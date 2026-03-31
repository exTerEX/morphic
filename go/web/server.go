package web

import (
	"embed"
	"html/template"
	"io/fs"
	"net/http"

	"github.com/gin-gonic/gin"
)

//go:embed templates static
var webFS embed.FS

// SetupRouter creates and configures the gin router with all routes.
func SetupRouter() *gin.Engine {
	r := gin.Default()

	// Parse templates from embedded FS
	tmpl := template.Must(template.ParseFS(webFS, "templates/*.html"))
	r.SetHTMLTemplate(tmpl)

	// Serve static files from embedded FS
	staticFS, _ := fs.Sub(webFS, "static")
	r.StaticFS("/static", http.FS(staticFS))

	// No-cache middleware (mirrors Python's @app.after_request)
	r.Use(func(c *gin.Context) {
		c.Header("Cache-Control", "no-cache, no-store, must-revalidate")
		c.Header("Pragma", "no-cache")
		c.Header("Expires", "0")
		c.Next()
	})

	// Index route
	r.GET("/", func(c *gin.Context) {
		c.HTML(http.StatusOK, "index.html", nil)
	})

	// Register API route groups
	registerSharedRoutes(r)
	registerOrganizerRoutes(r)

	return r
}
