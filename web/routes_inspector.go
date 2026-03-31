package web

import (
	"net/http"
	"os"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/exterex/morphic/internal/inspector"
)

func registerInspectorRoutes(r *gin.Engine) {
	g := r.Group("/api/inspector")
	{
		g.POST("/scan", handleInspectorScan)
		g.GET("/scan/:id/status", handleInspectorStatus)
		g.GET("/scan/:id/results", handleInspectorResults)
		g.POST("/exif/edit", handleExifEdit)
		g.POST("/exif/strip", handleExifStrip)
	}
}

func handleInspectorScan(c *gin.Context) {
	var req struct {
		Folder string `json:"folder"`
		Mode   string `json:"mode"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.Folder == "" || !isDir(req.Folder) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid folder: " + req.Folder})
		return
	}
	if req.Mode == "" {
		req.Mode = "exif"
	}
	if req.Mode != "exif" && req.Mode != "integrity" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "mode must be 'exif' or 'integrity'"})
		return
	}

	jobID := inspector.StartJob(req.Folder, req.Mode)
	c.JSON(http.StatusAccepted, gin.H{"job_id": jobID})
}

func handleInspectorStatus(c *gin.Context) {
	id := c.Param("id")
	job, ok := inspector.GetJob(id)
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
		"mode":            job.Mode,
		"progress":        job.Progress,
		"message":         job.Message,
		"error":           job.Error,
		"total_files":     job.Total,
		"processed_files": job.Processed,
		"elapsed_seconds": round1(elapsed),
	})
}

func handleInspectorResults(c *gin.Context) {
	id := c.Param("id")
	job, ok := inspector.GetJob(id)
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "Job not found"})
		return
	}

	if job.Status != "done" && job.Status != "failed" {
		c.JSON(http.StatusConflict, gin.H{"error": "Scan not finished yet"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"mode":        job.Mode,
		"results":     job.Results,
		"total_files": job.Total,
	})
}

func handleExifEdit(c *gin.Context) {
	var req struct {
		File    string                 `json:"file"`
		Updates map[string]interface{} `json:"updates"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if req.File == "" || !isFile(req.File) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid file: " + req.File})
		return
	}
	if len(req.Updates) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "No updates provided"})
		return
	}

	// EXIF editing with go-exif is read-only; for now return not-implemented
	// to match the API contract. A future iteration could use a subprocess.
	c.JSON(http.StatusNotImplemented, gin.H{
		"error": "EXIF editing is not yet supported in the Go version",
	})
}

func handleExifStrip(c *gin.Context) {
	var req struct {
		Files []string `json:"files"`
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if len(req.Files) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "No files specified"})
		return
	}

	results := inspector.StripExifBatch(req.Files)
	successCount := 0
	for _, r := range results {
		if s, ok := r["success"].(bool); ok && s {
			successCount++
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"results":       results,
		"total":         len(req.Files),
		"success_count": successCount,
	})
}

func isFile(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

func isDir(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

func round1(f float64) float64 {
	return float64(int(f*10+0.5)) / 10
}
