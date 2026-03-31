package web

import (
	"mime"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/exterex/morphic/internal/shared"
)

func registerSharedRoutes(r *gin.Engine) {
	r.GET("/api/browse", handleBrowseDirectory)
	r.POST("/api/browse/native", handleBrowseNative)
	r.GET("/api/thumbnail", handleThumbnail)
	r.GET("/api/system_info", handleSystemInfo)
	r.GET("/api/media", handleMedia)
}

// handleBrowseDirectory lists directories for the in-page folder browser.
func handleBrowseDirectory(c *gin.Context) {
	path := c.Query("path")
	if path == "" {
		home, _ := os.UserHomeDir()
		path = home
	}

	path = filepath.Clean(path)
	info, err := os.Stat(path)
	if err != nil || !info.IsDir() {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Not a directory"})
		return
	}

	entries, _ := os.ReadDir(path)
	type dirEntry struct {
		Name string `json:"name"`
		Path string `json:"path"`
		Type string `json:"type"`
	}
	var dirs []dirEntry
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), ".") {
			continue
		}
		if e.IsDir() {
			dirs = append(dirs, dirEntry{
				Name: e.Name(),
				Path: filepath.Join(path, e.Name()),
				Type: "directory",
			})
		}
	}
	sort.Slice(dirs, func(i, j int) bool {
		return strings.ToLower(dirs[i].Name) < strings.ToLower(dirs[j].Name)
	})

	parent := filepath.Dir(path)
	var parentPtr interface{} = parent
	if parent == path {
		parentPtr = nil
	}

	c.JSON(http.StatusOK, gin.H{
		"current": path,
		"parent":  parentPtr,
		"entries": dirs,
	})
}

// handleBrowseNative opens the OS-native folder picker dialog.
func handleBrowseNative(c *gin.Context) {
	folder, err := shared.OpenNativeFolderDialog()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if folder == "" {
		c.JSON(http.StatusOK, gin.H{
			"folder":  nil,
			"message": "Dialog cancelled or unavailable",
		})
		return
	}
	c.JSON(http.StatusOK, gin.H{"folder": folder})
}

func handleThumbnail(c *gin.Context) {
	path := c.Query("path")
	if path == "" {
		c.Status(http.StatusBadRequest)
		return
	}

	var data []byte
	var err error

	if shared.IsVideoFile(path) {
		data, err = shared.GenerateVideoThumbnail(path, shared.DefaultThumbnailSize)
	} else {
		data, err = shared.GenerateImageThumbnail(path, shared.DefaultThumbnailSize)
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "thumbnail generation failed", "detail": err.Error()})
		return
	}

	c.Data(http.StatusOK, "image/jpeg", data)
}

func handleSystemInfo(c *gin.Context) {
	ffmpegInfo := gin.H{
		"installed":      false,
		"hwaccels":       []string{},
		"encoders":       []string{},
		"nvenc_available": false,
	}

	if _, err := exec.LookPath("ffmpeg"); err == nil {
		ffmpegInfo["installed"] = true

		if out, err := exec.Command("ffmpeg", "-hide_banner", "-encoders").
			CombinedOutput(); err == nil {
			var encoders []string
			for _, line := range strings.Split(string(out), "\n") {
				line = strings.TrimSpace(line)
				if len(line) > 0 && (line[0] == 'V' || line[0] == 'A') {
					encoders = append(encoders, line)
				}
			}
			ffmpegInfo["encoders"] = encoders
			for _, e := range encoders {
				if strings.Contains(e, "nvenc") {
					ffmpegInfo["nvenc_available"] = true
					break
				}
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"version":  shared.Version,
		"platform": runtime.GOOS,
		"arch":     runtime.GOARCH,
		"go":       runtime.Version(),
		"cpus":     runtime.NumCPU(),
		"ffmpeg":   ffmpegInfo,
	})
}

// handleMedia serves a media file for full-size preview.
func handleMedia(c *gin.Context) {
	filePath := c.Query("path")
	if filePath == "" {
		c.Status(http.StatusBadRequest)
		return
	}

	filePath = filepath.Clean(filePath)
	info, err := os.Stat(filePath)
	if err != nil || info.IsDir() {
		c.Status(http.StatusNotFound)
		return
	}

	ext := shared.NormaliseExt(filepath.Ext(filePath))
	_, isImg := shared.ImageExtensions[ext]
	_, isVid := shared.VideoExtensions[ext]
	if !isImg && !isVid {
		c.Status(http.StatusForbidden)
		return
	}

	contentType := mime.TypeByExtension(filepath.Ext(filePath))
	if contentType == "" {
		contentType = "application/octet-stream"
	}
	c.File(filePath)
}
