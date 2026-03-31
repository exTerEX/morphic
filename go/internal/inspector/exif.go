package inspector

import (
	"fmt"
	"math"
	"os"

	exif "github.com/dsoprea/go-exif/v3"
	exifcommon "github.com/dsoprea/go-exif/v3/common"
)

// ExifData is a flat map of human-readable tag names to values.
type ExifData map[string]interface{}

// ReadExif reads EXIF metadata from an image file and returns a flat
// map of tag names to decoded values. Includes "_gps_lat" and "_gps_lng"
// when GPS data is present.
func ReadExif(path string) (ExifData, error) {
	if _, err := os.Stat(path); err != nil {
		return nil, fmt.Errorf("file not found: %s", path)
	}

	rawExif, err := exif.SearchFileAndExtractExif(path)
	if err != nil {
		// No EXIF data found — not an error, just empty
		return ExifData{}, nil
	}

	tags, _, err := exif.GetFlatExifData(rawExif, nil)
	if err != nil {
		return ExifData{}, nil
	}

	result := make(ExifData, len(tags))
	var latVal, lngVal []exifcommon.Rational
	var latRef, lngRef string

	for _, tag := range tags {
		name := tag.TagName
		result[name] = tag.FormattedFirst

		// Collect GPS fields for decimal conversion
		switch tag.TagName {
		case "GPSLatitude":
			if vals, ok := tag.Value.([]exifcommon.Rational); ok {
				latVal = vals
			}
		case "GPSLatitudeRef":
			latRef = tag.FormattedFirst
		case "GPSLongitude":
			if vals, ok := tag.Value.([]exifcommon.Rational); ok {
				lngVal = vals
			}
		case "GPSLongitudeRef":
			lngRef = tag.FormattedFirst
		}
	}

	// Compute decimal GPS coordinates
	if len(latVal) >= 3 && len(lngVal) >= 3 {
		result["_gps_lat"] = gpsToDecimal(latVal, latRef)
		result["_gps_lng"] = gpsToDecimal(lngVal, lngRef)
	}

	return result, nil
}

// gpsToDecimal converts DMS rational values to decimal degrees.
func gpsToDecimal(coords []exifcommon.Rational, ref string) float64 {
	deg := float64(coords[0].Numerator) / float64(coords[0].Denominator)
	min := float64(coords[1].Numerator) / float64(coords[1].Denominator)
	sec := float64(coords[2].Numerator) / float64(coords[2].Denominator)
	decimal := deg + min/60 + sec/3600
	if ref == "S" || ref == "W" {
		decimal = -decimal
	}
	return math.Round(decimal*1e6) / 1e6
}

// StripExif removes all EXIF metadata from an image file by reading the
// image data and rewriting it without the EXIF segment. For JPEG files this
// uses piexif-style segment removal.
func StripExif(path string) error {
	if _, err := os.Stat(path); err != nil {
		return fmt.Errorf("file not found: %s", path)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}

	// Check if there's EXIF to strip
	_, err = exif.SearchAndExtractExif(data)
	if err != nil {
		// No EXIF to strip
		return nil
	}

	stripped, err := dropExifFromJPEG(data)
	if err != nil {
		return err
	}

	return os.WriteFile(path, stripped, 0644)
}

// dropExifFromJPEG removes APP1 (EXIF) segments from JPEG data.
func dropExifFromJPEG(data []byte) ([]byte, error) {
	if len(data) < 2 || data[0] != 0xFF || data[1] != 0xD8 {
		return nil, fmt.Errorf("not a JPEG file")
	}

	out := []byte{0xFF, 0xD8}
	i := 2
	for i < len(data)-1 {
		if data[i] != 0xFF {
			// Reached image data, copy the rest
			out = append(out, data[i:]...)
			break
		}
		marker := data[i+1]

		// SOS (start of scan) — everything after this is image data
		if marker == 0xDA {
			out = append(out, data[i:]...)
			break
		}

		// Markers without length
		if marker == 0xD8 || marker == 0xD9 || (marker >= 0xD0 && marker <= 0xD7) {
			out = append(out, data[i], data[i+1])
			i += 2
			continue
		}

		if i+3 >= len(data) {
			out = append(out, data[i:]...)
			break
		}

		segLen := int(data[i+2])<<8 | int(data[i+3])
		segEnd := i + 2 + segLen
		if segEnd > len(data) {
			segEnd = len(data)
		}

		// APP1 marker (0xE1) is where EXIF lives — skip it
		if marker == 0xE1 {
			i = segEnd
			continue
		}

		out = append(out, data[i:segEnd]...)
		i = segEnd
	}

	return out, nil
}

// StripExifBatch strips EXIF from multiple files and returns per-file results.
func StripExifBatch(paths []string) map[string]map[string]interface{} {
	results := make(map[string]map[string]interface{}, len(paths))
	for _, p := range paths {
		err := StripExif(p)
		if err != nil {
			results[p] = map[string]interface{}{"success": false, "error": err.Error()}
		} else {
			results[p] = map[string]interface{}{"success": true}
		}
	}
	return results
}
