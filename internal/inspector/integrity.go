package inspector

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"

	"github.com/disintegration/imaging"
	"github.com/exterex/morphic/internal/shared"
)

// IntegrityResult holds the outcome of a single file check.
type IntegrityResult struct {
	Path          string  `json:"path"`
	Valid         bool    `json:"valid"`
	Error         string  `json:"error,omitempty"`
	Size          int64   `json:"size"`
	SizeFormatted string  `json:"size_formatted"`
	Width         int     `json:"width"`
	Height        int     `json:"height"`
	Format        string  `json:"format,omitempty"`
	Duration      float64 `json:"duration,omitempty"`
	Codec         string  `json:"codec,omitempty"`
	Type          string  `json:"type"`
	Filename      string  `json:"filename,omitempty"`
	Directory     string  `json:"directory,omitempty"`
}

// CheckImage validates an image file by opening and decoding it.
func CheckImage(path string) IntegrityResult {
	r := IntegrityResult{Path: path, Type: "image"}

	info, err := os.Stat(path)
	if err != nil {
		r.Error = "File not found"
		return r
	}
	r.Size = info.Size()
	r.SizeFormatted = shared.FormatFileSize(r.Size)

	if r.Size == 0 {
		r.Error = "Zero-byte file"
		return r
	}

	ext := strings.ToLower(filepath.Ext(path))
	if alias, ok := shared.Aliases[ext]; ok {
		ext = alias
	}

	if ext == ".avif" {
		// Use ffprobe for AVIF validation because imaging may not decode it.
		cmd := exec.Command("ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height", "-of", "csv=p=0", path)
		out, err := cmd.Output()
		if err != nil {
			r.Error = err.Error()
			return r
		}
		parts := strings.Split(strings.TrimSpace(string(out)), ",")
		if len(parts) >= 2 {
			r.Width, _ = strconv.Atoi(parts[1])
		}
		if len(parts) >= 3 {
			r.Height, _ = strconv.Atoi(parts[2])
		}
		if len(parts) >= 1 {
			r.Format = parts[0]
		}
		r.Valid = true
		return r
	}

	img, err := imaging.Open(path)
	if err != nil {
		r.Error = err.Error()
		return r
	}

	bounds := img.Bounds()
	r.Width = bounds.Dx()
	r.Height = bounds.Dy()
	r.Valid = true
	return r
}

// CheckVideo validates a video file using ffprobe.
func CheckVideo(path string) IntegrityResult {
	r := IntegrityResult{Path: path, Type: "video"}

	info, err := os.Stat(path)
	if err != nil {
		r.Error = "File not found"
		return r
	}
	r.Size = info.Size()
	r.SizeFormatted = shared.FormatFileSize(r.Size)

	if r.Size == 0 {
		r.Error = "Zero-byte file"
		return r
	}

	cmd := exec.Command("ffprobe",
		"-v", "error",
		"-select_streams", "v:0",
		"-show_entries", "stream=codec_name,width,height,duration",
		"-of", "csv=p=0",
		path,
	)

	out, err := cmd.Output()
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			stderr := strings.TrimSpace(string(exitErr.Stderr))
			if stderr != "" {
				r.Error = stderr
			} else {
				r.Error = fmt.Sprintf("ffprobe exit code %d", exitErr.ExitCode())
			}
		} else {
			r.Error = err.Error()
		}
		return r
	}

	output := strings.TrimSpace(string(out))
	if output == "" {
		r.Error = "No video stream found"
		return r
	}

	parts := strings.Split(output, ",")
	if len(parts) >= 1 {
		r.Codec = parts[0]
	}
	if len(parts) >= 2 {
		r.Width, _ = strconv.Atoi(parts[1])
	}
	if len(parts) >= 3 {
		r.Height, _ = strconv.Atoi(parts[2])
	}
	if len(parts) >= 4 && parts[3] != "" {
		r.Duration, _ = strconv.ParseFloat(parts[3], 64)
	}

	r.Valid = true
	return r
}

// CheckFiles checks integrity of all media files in a folder using
// concurrent goroutines.
func CheckFiles(folder string, maxWorkers int) ([]IntegrityResult, error) {
	allExts := make(map[string]struct{})
	for k, v := range shared.ImageExtensions {
		allExts[k] = v
	}
	for k, v := range shared.VideoExtensions {
		allExts[k] = v
	}

	files, err := shared.FindFilesByExtension(folder, allExts, shared.ExcludedFolders)
	if err != nil {
		return nil, err
	}

	results := make([]IntegrityResult, len(files))
	var wg sync.WaitGroup
	sem := make(chan struct{}, maxWorkers)

	for i, fi := range files {
		wg.Add(1)
		sem <- struct{}{}
		go func(idx int, f shared.FileInfo) {
			defer wg.Done()
			defer func() { <-sem }()

			if shared.IsImage(f.Path) {
				results[idx] = CheckImage(f.Path)
			} else if shared.IsVideo(f.Path) {
				results[idx] = CheckVideo(f.Path)
			} else {
				results[idx] = IntegrityResult{
					Path:  f.Path,
					Type:  "unknown",
					Error: "Unknown file type",
				}
			}
		}(i, fi)
	}

	wg.Wait()
	return results, nil
}
