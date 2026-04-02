package converter

import (
	"sort"
	"strings"

	"github.com/exterex/morphic/internal/shared"
)

// Canonical image formats we can write to.
var canonicalImage = map[string]struct{}{
	".jpg":  {},
	".png":  {},
	".tif":  {},
	".bmp":  {},
	".webp": {},
	".gif":  {},
	".ico":  {},
	".avif": {},
}

// Canonical video formats we can write to.
var canonicalVideo = map[string]struct{}{
	".mp4":  {},
	".mov":  {},
	".avi":  {},
	".mkv":  {},
	".webm": {},
	".flv":  {},
	".wmv":  {},
	".m4v":  {},
	".mpeg": {},
	".3gp":  {},
	".ts":   {},
}

// ImageConversions maps source image extension to list of target extensions.
var ImageConversions map[string][]string

// VideoConversions maps source video extension to list of target extensions.
var VideoConversions map[string][]string

func init() {
	ImageConversions = make(map[string][]string)
	for ext := range shared.ImageExtensions {
		norm := shared.NormaliseExt(ext)
		if _, ok := canonicalImage[norm]; !ok {
			continue
		}
		var targets []string
		for t := range canonicalImage {
			if t != norm {
				targets = append(targets, t)
			}
		}
		sort.Strings(targets)
		ImageConversions[ext] = targets
	}

	VideoConversions = make(map[string][]string)
	for ext := range shared.VideoExtensions {
		norm := shared.NormaliseExt(ext)
		if _, ok := canonicalVideo[norm]; !ok {
			continue
		}
		var targets []string
		for t := range canonicalVideo {
			if t != norm {
				targets = append(targets, t)
			}
		}
		sort.Strings(targets)
		VideoConversions[ext] = targets
	}
}

// GetCompatibleTargets returns the list of extensions a source can convert to.
func GetCompatibleTargets(sourcePath string) []string {
	ext := shared.NormaliseExt(strings.ToLower(extOf(sourcePath)))
	if targets, ok := ImageConversions[ext]; ok {
		return targets
	}
	if targets, ok := VideoConversions[ext]; ok {
		return targets
	}
	return nil
}

func extOf(path string) string {
	for i := len(path) - 1; i >= 0; i-- {
		if path[i] == '.' {
			return path[i:]
		}
	}
	return ""
}
