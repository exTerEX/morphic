package web

import (
	"net/http"
	"runtime"

	"github.com/gin-gonic/gin"
	"github.com/exterex/morphic/internal/shared"
)

func registerSharedRoutes(r *gin.Engine) {
	r.POST("/api/browse", handleBrowse)
	r.GET("/api/thumbnail", handleThumbnail)
	r.GET("/api/system-info", handleSystemInfo)
}

func handleBrowse(c *gin.Context) {
	folder, err := shared.OpenNativeFolderDialog()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	if folder == "" {
		c.JSON(http.StatusOK, gin.H{"folder": nil})
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
		c.Status(http.StatusInternalServerError)
		return
	}

	c.Data(http.StatusOK, "image/jpeg", data)
}

func handleSystemInfo(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{
		"version":  shared.Version,
		"platform": runtime.GOOS,
		"arch":     runtime.GOARCH,
		"go":       runtime.Version(),
		"cpus":     runtime.NumCPU(),
	})
}
