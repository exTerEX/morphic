package web

import (
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/exterex/morphic/internal/organizer"
)

func registerOrganizerRoutes(r *gin.Engine) {
	g := r.Group("/api/organizer")
	{
		g.POST("/scan", handleOrganizerScan)
		g.POST("/execute/:id", handleOrganizerExecute)
		g.GET("/status/:id", handleOrganizerStatus)
	}
}

func handleOrganizerScan(c *gin.Context) {
	var req struct {
		Folder      string `json:"folder"`
		Mode        string `json:"mode"`
		Template    string `json:"template"`
		Destination string `json:"destination"`
		Operation   string `json:"operation"`
		ScanType    string `json:"scan_type"`
	}

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	if req.Folder == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "folder is required"})
		return
	}

	jobID := organizer.StartPlanJob(
		req.Folder, req.Mode, req.Template,
		req.Destination, req.Operation, req.ScanType,
	)

	c.JSON(http.StatusAccepted, gin.H{"job_id": jobID})
}

func handleOrganizerExecute(c *gin.Context) {
	id := c.Param("id")
	if !organizer.ExecuteJob(id) {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found or not in planned state"})
		return
	}

	c.JSON(http.StatusAccepted, gin.H{"status": "executing"})
}

func handleOrganizerStatus(c *gin.Context) {
	id := c.Param("id")
	job, ok := organizer.GetJob(id)
	if !ok {
		c.JSON(http.StatusNotFound, gin.H{"error": "job not found"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"id":          job.ID,
		"status":      job.Status,
		"phase":       job.Phase,
		"progress":    job.Progress,
		"message":     job.Message,
		"error":       job.Error,
		"total":       job.Total,
		"processed":   job.Processed,
		"sort_plan":   job.SortPlan,
		"rename_plan": job.RenamePlan,
	})
}
