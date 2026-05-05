package shared

import (
	"bytes"
	"fmt"
	"image"
	"image/jpeg"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"

	"github.com/disintegration/imaging"
)

const (
	DefaultThumbnailSize    = 200
	DefaultThumbnailQuality = 80
)

// ThumbnailCache provides a thread-safe cache for generated thumbnails.
type ThumbnailCache struct {
	mu    sync.RWMutex
	store map[string][]byte
}

var thumbnailCache = &ThumbnailCache{
	store: make(map[string][]byte),
}

// GenerateImageThumbnail creates a JPEG thumbnail for an image file.
func GenerateImageThumbnail(path string, size int) ([]byte, error) {
	if size <= 0 {
		size = DefaultThumbnailSize
	}

	cacheKey := fmt.Sprintf("%s:%d", path, size)
	thumbnailCache.mu.RLock()
	if data, ok := thumbnailCache.store[cacheKey]; ok {
		thumbnailCache.mu.RUnlock()
		return data, nil
	}
	thumbnailCache.mu.RUnlock()

	ext := strings.ToLower(filepath.Ext(path))
	if alias, ok := Aliases[ext]; ok {
		ext = alias
	}

	if ext == ".avif" {
		data, err := extractImageFrame(path, "00:00:00", size)
		if err != nil {
			return nil, fmt.Errorf("failed to generate AVIF thumbnail %s: %w", path, err)
		}

		thumbnailCache.mu.Lock()
		thumbnailCache.store[cacheKey] = data
		thumbnailCache.mu.Unlock()

		return data, nil
	}

	img, err := imaging.Open(path, imaging.AutoOrientation(true))
	if err != nil {
		// Fallback to ffmpeg for formats that imaging can't decode.
		ffData, ffErr := extractImageFrame(path, "00:00:00", size)
		if ffErr == nil {
			thumbnailCache.mu.Lock()
			thumbnailCache.store[cacheKey] = ffData
			thumbnailCache.mu.Unlock()
			return ffData, nil
		}
		return nil, fmt.Errorf("failed to open image %s: %w (ffmpeg fallback: %v)", path, err, ffErr)
	}

	thumb := imaging.Fit(img, size, size, imaging.Lanczos)

	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, thumb, &jpeg.Options{Quality: DefaultThumbnailQuality}); err != nil {
		return nil, fmt.Errorf("failed to encode thumbnail: %w", err)
	}

	data := buf.Bytes()
	thumbnailCache.mu.Lock()
	thumbnailCache.store[cacheKey] = data
	thumbnailCache.mu.Unlock()

	return data, nil
}

// GenerateVideoThumbnail creates a JPEG thumbnail for a video file using ffmpeg.
func GenerateVideoThumbnail(path string, size int) ([]byte, error) {
	if size <= 0 {
		size = DefaultThumbnailSize
	}

	cacheKey := fmt.Sprintf("video:%s:%d", path, size)
	thumbnailCache.mu.RLock()
	if data, ok := thumbnailCache.store[cacheKey]; ok {
		thumbnailCache.mu.RUnlock()
		return data, nil
	}
	thumbnailCache.mu.RUnlock()

	// Try extracting frame at 1 second, fallback to 0 seconds
	data, err := extractVideoFrame(path, "00:00:01", size)
	if err != nil {
		data, err = extractVideoFrame(path, "00:00:00", size)
		if err != nil {
			return nil, fmt.Errorf("failed to extract video frame from %s: %w", path, err)
		}
	}

	thumbnailCache.mu.Lock()
	thumbnailCache.store[cacheKey] = data
	thumbnailCache.mu.Unlock()

	return data, nil
}

func extractVideoFrame(videoPath, seekTime string, size int) ([]byte, error) {
	img, err := extractImageFromFFmpeg(videoPath, seekTime, size)
	if err != nil {
		return nil, err
	}

	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, imaging.Fit(img, size, size, imaging.Lanczos), &jpeg.Options{Quality: DefaultThumbnailQuality}); err != nil {
		return nil, err
	}

	return buf.Bytes(), nil
}

func extractImageFrame(imagePath, seekTime string, size int) ([]byte, error) {
	img, err := extractImageFromFFmpeg(imagePath, seekTime, size)
	if err != nil {
		return nil, err
	}

	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, imaging.Fit(img, size, size, imaging.Lanczos), &jpeg.Options{Quality: DefaultThumbnailQuality}); err != nil {
		return nil, err
	}

	return buf.Bytes(), nil
}

func ffmpegCandidates() []string {
	var bins []string
	for _, name := range []string{"ffmpeg"} {
		if _, err := exec.LookPath(name); err == nil {
			bins = append(bins, name)
		}
	}
	return bins
}

// OpenImageFile opens an image from any format supported by imaging or ffmpeg.
// It uses imaging.Open for common formats and falls back to ffmpeg for formats
// that imaging cannot handle (e.g. AVIF).
func OpenImageFile(path string) (image.Image, error) {
	img, err := imaging.Open(path, imaging.AutoOrientation(true))
	if err == nil {
		return img, nil
	}
	// imaging failed — try ffmpeg (handles AVIF, HEIC, …)
	return extractImageFromFFmpeg(path, "00:00:00", 0)
}

func extractImageFromFFmpeg(srcPath, seekTime string, size int) (image.Image, error) {
	bins := ffmpegCandidates()
	if len(bins) == 0 {
		return nil, fmt.Errorf("ffmpeg not found in PATH")
	}

	var lastErr error
	for _, bin := range bins {
		for _, codec := range []string{"png", "mjpeg"} {
			args := []string{"-ss", seekTime, "-i", srcPath, "-frames:v", "1"}
			if size > 0 {
				args = append(args, "-vf", fmt.Sprintf("scale=%d:%d:force_original_aspect_ratio=decrease", size, size))
			}
			args = append(args, "-f", "image2pipe", "-vcodec", codec)
			if codec == "mjpeg" {
				args = append(args, "-q:v", "5")
			}
			args = append(args, "pipe:1")

			var stdout, stderr bytes.Buffer
			cmd := exec.Command(bin, args...)
			cmd.Stdout = &stdout
			cmd.Stderr = &stderr

			if err := cmd.Run(); err != nil {
				lastErr = fmt.Errorf("%s/%s failed: %w (stderr: %s)", bin, codec, err, stderr.String())
				continue
			}
			if stdout.Len() == 0 {
				lastErr = fmt.Errorf("%s/%s: no output produced", bin, codec)
				continue
			}

			img, _, err := image.Decode(bytes.NewReader(stdout.Bytes()))
			if err != nil {
				lastErr = fmt.Errorf("%s/%s: decode failed: %w", bin, codec, err)
				continue
			}
			return img, nil
		}
	}
	return nil, fmt.Errorf("all ffmpeg variants failed for %s: %w", srcPath, lastErr)
}

// IsImageFile checks if a path has an image extension.
func IsImageFile(path string) bool {
	ext := strings.ToLower(filepath.Ext(path))
	if alias, ok := Aliases[ext]; ok {
		ext = alias
	}
	_, ok := ImageExtensions[ext]
	return ok
}

// IsVideoFile checks if a path has a video extension.
func IsVideoFile(path string) bool {
	ext := strings.ToLower(filepath.Ext(path))
	if alias, ok := Aliases[ext]; ok {
		ext = alias
	}
	_, ok := VideoExtensions[ext]
	return ok
}
