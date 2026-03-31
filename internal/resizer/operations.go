package resizer

import (
	"fmt"
	"image"
	"image/color"
	"image/draw"
	"image/png"
	"os"
	"path/filepath"
	"strings"

	"github.com/disintegration/imaging"
)

// ResizeModes lists the valid resize mode strings.
var ResizeModes = []string{"fit", "fill", "stretch", "pad"}

// IsValidMode returns true if mode is one of the accepted values.
func IsValidMode(mode string) bool {
	for _, m := range ResizeModes {
		if m == mode {
			return true
		}
	}
	return false
}

// ResizeImage resizes a single image.
//
// Modes:
//   - "fit":     resize to fit within width×height, preserving aspect ratio
//   - "fill":    resize to cover width×height then center-crop
//   - "stretch": resize to exact width×height ignoring ratio
//   - "pad":     fit + pad borders with bgColor
//
// Returns the path to the output file.
func ResizeImage(
	path string,
	width, height int,
	mode string,
	outputFolder string,
	bgColor string,
	quality int,
	outputFormat string,
) (string, error) {
	if _, err := os.Stat(path); err != nil {
		return "", fmt.Errorf("file not found: %s", path)
	}
	if !IsValidMode(mode) {
		return "", fmt.Errorf("invalid mode '%s'", mode)
	}
	if width <= 0 || height <= 0 {
		return "", fmt.Errorf("width and height must be positive")
	}

	img, err := imaging.Open(path)
	if err != nil {
		return "", err
	}

	var result *image.NRGBA

	switch mode {
	case "fit":
		result = imaging.Fit(img, width, height, imaging.Lanczos)
	case "fill":
		result = imaging.Fill(img, width, height, imaging.Center, imaging.Lanczos)
	case "stretch":
		result = imaging.Resize(img, width, height, imaging.Lanczos)
	case "pad":
		fitted := imaging.Fit(img, width, height, imaging.Lanczos)
		bg := parseHexColor(bgColor)
		canvas := imaging.New(width, height, bg)
		offsetX := (width - fitted.Bounds().Dx()) / 2
		offsetY := (height - fitted.Bounds().Dy()) / 2
		draw.Draw(canvas, image.Rect(offsetX, offsetY,
			offsetX+fitted.Bounds().Dx(), offsetY+fitted.Bounds().Dy()),
			fitted, image.Point{}, draw.Over)
		result = canvas
	}

	// Determine output path
	srcExt := filepath.Ext(path)
	ext := outputFormat
	if ext == "" {
		ext = srcExt
	}
	if !strings.HasPrefix(ext, ".") {
		ext = "." + ext
	}

	stem := strings.TrimSuffix(filepath.Base(path), srcExt)
	var dest string
	if outputFolder != "" {
		os.MkdirAll(outputFolder, 0755)
		dest = filepath.Join(outputFolder, stem+ext)
	} else {
		dest = filepath.Join(filepath.Dir(path), stem+ext)
	}

	// imaging.Save handles format detection from extension
	opts := []imaging.EncodeOption{}
	extLower := strings.ToLower(ext)
	if extLower == ".jpg" || extLower == ".jpeg" || extLower == ".webp" {
		opts = append(opts, imaging.JPEGQuality(quality))
	}
	if extLower == ".png" {
		opts = append(opts, imaging.PNGCompressionLevel(png.DefaultCompression))
	}

	if err := imaging.Save(result, dest, opts...); err != nil {
		return "", err
	}

	return dest, nil
}

// parseHexColor parses a CSS hex colour like "#FF0000" to a color.NRGBA.
func parseHexColor(s string) color.NRGBA {
	s = strings.TrimPrefix(s, "#")
	if len(s) != 6 {
		return color.NRGBA{A: 255} // fallback to black
	}
	var r, g, b uint8
	fmt.Sscanf(s, "%02x%02x%02x", &r, &g, &b)
	return color.NRGBA{R: r, G: g, B: b, A: 255}
}
