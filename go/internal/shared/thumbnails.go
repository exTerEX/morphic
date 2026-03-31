package shared

import (
	"bytes"
	"fmt"
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

	img, err := imaging.Open(path, imaging.AutoOrientation(true))
	if err != nil {
		return nil, fmt.Errorf("failed to open image %s: %w", path, err)
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
	cmd := exec.Command("ffmpeg",
		"-ss", seekTime,
		"-i", videoPath,
		"-vframes", "1",
		"-vf", fmt.Sprintf("scale=%d:%d:force_original_aspect_ratio=decrease", size, size),
		"-f", "image2pipe",
		"-vcodec", "mjpeg",
		"-q:v", "5",
		"pipe:1",
	)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("ffmpeg failed: %w, stderr: %s", err, stderr.String())
	}

	return stdout.Bytes(), nil
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
