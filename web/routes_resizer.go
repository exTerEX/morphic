package web

import (
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/exterex/morphic/internal/resizer"
)

func registerResizerRoutes(r *gin.Engine) {
	g := r.Group("/api/resizer")
	{
		g.POST("/scan", handleResizerScan)
		g.GET("/scan/:id/status", handleResizerStatus)
		g.GET("/scan/:id/results", handleResizerResults)
	}
}

func handleResizerScan(c *gin.Context) {
	var req struct {
		Folder       string `json:"folder"`
		Width        int    `json:"width"`
		Height       int    `json:"height"`
		Mode         string `json:"mode"`
		BgColor      string `json:"bg_color"`
		Quality      int    `json:"quality"`
		OutputFolder string `json:"output_folder"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.Folder == "" || !isDir(req.Folder) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid folder: " + req.Folder})
		return
	}
	if req.Width <= 0 || req.Height <= 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "width and height must be positive"})
		return
	}
	if req.Mode == "" {
		req.Mode = "fit"
	}
	if !resizer.IsValidMode(req.Mode) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "mode must be one of fit, fill, stretch, pad"})
		return
	}
	if req.BgColor == "" {
		req.BgColor = "#000000"
	}
	if req.Quality == 0 {
		req.Quality = 90
	}

	jobID := resizer.StartJob(
		req.Folder, req.Width, req.Height, req.Mode,
		req.OutputFolder, req.BgColor, req.Quality,
	)
	c.JSON(http.StatusAccepted, gin.H{"job_id": jobID})
}

func handleResizerStatus(c *gin.Context) {
	id := c.Param("id")
	job, ok := resizer.GetJob(id)
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "Job not found"})
		return
	}

	elapsed := 0.0
	if !job.StartedAt.IsZero() {
		end := job.DoneAt
		if end.IsZero() {
			end = time.Now()
		}
		elapsed = end.Sub(job.StartedAt).Seconds()
	}

	c.JSON(http.StatusOK, gin.H{
		"id":              job.ID,
		"status":          job.Status,
		"progress":        job.Progress,
		"message":         job.Message,
		"error":           job.Error,
		"total_files":     job.Total,
		"processed_files": job.Processed,
		"elapsed_seconds": round1(elapsed),
	})
}

func handleResizerResults(c *gin.Context) {
	id := c.Param("id")
	job, ok := resizer.GetJob(id)
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "Job not found"})
		return
	}

	if job.Status != "done" && job.Status != "failed" {
		c.JSON(http.StatusConflict, gin.H{"error": "Job not finished yet"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"results":         job.Results,
		"errors":          job.Errors,
		"total_files":     job.Total,
		"processed_files": job.Processed,
	})
}
