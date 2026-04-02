package converter

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/disintegration/imaging"
	"github.com/exterex/morphic/internal/shared"
)

// ffmpegAvailable checks if ffmpeg is on PATH.
func ffmpegAvailable() bool {
	_, err := exec.LookPath("ffmpeg")
	return err == nil
}

// ffmpegHasEncoder checks if ffmpeg has a particular video encoder.
func ffmpegHasEncoder(encoder string) bool {
	out, err := exec.Command("ffmpeg", "-hide_banner", "-encoders").Output()
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(out), "\n") {
		if strings.Contains(line, encoder) {
			return true
		}
	}
	return false
}

// getVideoEncoder selects a video encoder for the target extension.
// Returns (encoder, useHwaccel, outputExtension).
func getVideoEncoder(targetExt string) (string, bool, string) {
	ext := strings.ToLower(strings.TrimPrefix(targetExt, "."))
	outputExt := ext

	// AV1 variants (e.g., "mp4-av1")
	if strings.HasSuffix(ext, "-av1") {
		outputExt = strings.Split(ext, "-")[0]
		if ffmpegHasEncoder("libsvtav1") {
			return "libsvtav1", false, outputExt
		}
		if ffmpegHasEncoder("libaom-av1") {
			return "libaom-av1", false, outputExt
		}
		if ffmpegHasEncoder("libvpx-vp9") {
			return "libvpx-vp9", false, outputExt
		}
		return "libx264", false, outputExt
	}

	// Standard containers
	switch outputExt {
	case "mp4", "mkv", "mov":
		return "libx264", false, outputExt
	case "webm":
		return "libvpx-vp9", false, outputExt
	case "avi":
		return "mpeg4", false, outputExt
	case "flv", "mpeg", "3gp", "ts":
		return "libx264", false, outputExt
	}

	return "libx264", false, outputExt
}

// ConvertImage converts an image file using the imaging library.
func ConvertImage(source, targetExt, outputDir string) (string, error) {
	ext := shared.NormaliseExt(normaliseTargetExt(targetExt))

	stem := strings.TrimSuffix(filepath.Base(source), filepath.Ext(source))
	var dest string
	if outputDir != "" {
		os.MkdirAll(outputDir, 0755)
		dest = filepath.Join(outputDir, stem+ext)
	} else {
		dest = filepath.Join(filepath.Dir(source), stem+ext)
	}

	// Avoid overwriting
	if _, err := os.Stat(dest); err == nil {
		dest = filepath.Join(filepath.Dir(dest),
			strings.TrimSuffix(filepath.Base(dest), ext)+"_converted"+ext)
	}

	sourceExt := shared.NormaliseExt(strings.ToLower(filepath.Ext(source)))
	if sourceExt == ".avif" || ext == ".avif" {
		return convertImageByFFmpeg(source, dest, ext)
	}

	img, err := imaging.Open(source)
	if err != nil {
		// Relax: fallback to ffmpeg conversion for special unsupported formats
		return convertImageByFFmpeg(source, dest, ext)
	}

	opts := []imaging.EncodeOption{}
	extLower := strings.ToLower(ext)
	if extLower == ".jpg" || extLower == ".jpeg" {
		opts = append(opts, imaging.JPEGQuality(95))
	}

	if err := imaging.Save(img, dest, opts...); err != nil {
		// Fallback to ffmpeg for formats imaging can't encode
		return convertImageByFFmpeg(source, dest, ext)
	}

	return dest, nil
}

func convertImageByFFmpeg(source, dest, ext string) (string, error) {
	if !ffmpegAvailable() {
		return "", fmt.Errorf("ffmpeg is not installed or not on PATH")
	}

	cmd := []string{"ffmpeg", "-y", "-i", source}

	extLower := strings.ToLower(ext)
	if extLower == ".avif" {
		// AV1 (YUV 4:2:0) requires even dimensions and no alpha channel.
		// crop: trim 1px from odd dimensions. format=yuv420p: strip alpha (rgba → yuv420p).
		cmd = append(cmd, "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p")
		if ffmpegHasEncoder("libsvtav1") {
			cmd = append(cmd, "-c:v", "libsvtav1", "-crf", "28", "-preset", "8")
		} else if ffmpegHasEncoder("libaom-av1") {
			cmd = append(cmd, "-c:v", "libaom-av1", "-crf", "28", "-cpu-used", "4")
		} else {
			cmd = append(cmd, "-c:v", "libx264")
		}
	} else if extLower == ".webp" {
		cmd = append(cmd, "-c:v", "libwebp")
	} else if extLower == ".png" || extLower == ".jpg" || extLower == ".jpeg" || extLower == ".bmp" || extLower == ".gif" {
		// no explicit codec required
	} else {
		// generic fallback for unknown image extensions
	}

	cmd = append(cmd, dest)

	out, err := exec.Command(cmd[0], cmd[1:]...).CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("ffmpeg image conversion failed: %s", strings.TrimSpace(string(out)))
	}

	return dest, nil
}

// ConvertVideo converts a video file using ffmpeg.
func ConvertVideo(source, targetExt, outputDir string, av1CRF int) (string, error) {
	if !ffmpegAvailable() {
		return "", fmt.Errorf("ffmpeg is not installed or not on PATH")
	}

	ext := normaliseTargetExt(targetExt)

	codecTargetExt := ext
	if strings.Contains(ext, "-av1") {
		codecTargetExt = "." + strings.Split(strings.TrimPrefix(ext, "."), "-")[0]
	}

	stem := strings.TrimSuffix(filepath.Base(source), filepath.Ext(source))
	var dest string
	if outputDir != "" {
		os.MkdirAll(outputDir, 0755)
		dest = filepath.Join(outputDir, stem+codecTargetExt)
	} else {
		dest = filepath.Join(filepath.Dir(source), stem+codecTargetExt)
	}

	// Avoid overwriting
	if _, err := os.Stat(dest); err == nil {
		dest = filepath.Join(filepath.Dir(dest),
			strings.TrimSuffix(filepath.Base(dest), codecTargetExt)+"_converted"+codecTargetExt)
	}

	var cmd []string

	// Stream-copy for container-only conversions
	if codecTargetExt == ".mkv" || codecTargetExt == ".ts" {
		cmd = []string{"ffmpeg", "-y", "-i", source, "-c", "copy", dest}
	} else {
		encoder, _, _ := getVideoEncoder(targetExt)
		audioCodec := "aac"
		if codecTargetExt == ".avi" {
			audioCodec = "libmp3lame"
		}

		cmd = []string{"ffmpeg", "-y", "-i", source, "-c:v", encoder, "-c:a", audioCodec}

		if encoder == "libsvtav1" {
			crf := 28
			if av1CRF >= 10 && av1CRF <= 63 {
				crf = av1CRF
			}
			cmd = append(cmd, "-preset", "8", "-crf", fmt.Sprintf("%d", crf))
		} else if encoder == "libaom-av1" {
			crf := 28
			if av1CRF >= 10 && av1CRF <= 63 {
				crf = av1CRF
			}
			cmd = append(cmd, "-cpu-used", "4", "-crf", fmt.Sprintf("%d", crf))
		} else if strings.Contains(encoder, "av1") || strings.Contains(encoder, "vpx") {
			crf := 28
			if av1CRF >= 10 && av1CRF <= 63 {
				crf = av1CRF
			}
			cmd = append(cmd, "-crf", fmt.Sprintf("%d", crf))
		} else {
			cmd = append(cmd, "-preset", "fast", "-crf", "23")
		}

		cmd = append(cmd, dest)
	}

	out, err := exec.Command(cmd[0], cmd[1:]...).CombinedOutput()
	if err != nil {
		return "", fmt.Errorf("ffmpeg error: %s", strings.TrimSpace(string(out)))
	}

	return dest, nil
}

// ConvertFile is the high-level converter — routes to image or video handler.
func ConvertFile(source, targetExt, outputDir string, av1CRF int) (string, error) {
	if shared.IsImage(source) {
		return ConvertImage(source, targetExt, outputDir)
	}
	if shared.IsVideo(source) {
		return ConvertVideo(source, targetExt, outputDir, av1CRF)
	}
	return "", fmt.Errorf("unsupported file type: %s", source)
}

func normaliseTargetExt(ext string) string {
	if !strings.HasPrefix(ext, ".") {
		ext = "." + ext
	}
	return shared.NormaliseExt(ext)
}
