---
project: ProjektKraken
document: Webserver API Documentation
last_updated: 2026-01-25
status: Beta (V1)
---

# Webserver API

ProjektKraken includes an embedded FastAPI webserver that provides HTTP access to your world data. The server runs in a separate thread within the main application and can be accessed from web browsers or API clients.

## Overview

- **Framework:** FastAPI (async Python web framework)
- **Integration:** Runs in QThread via `WebServiceManager`
- **Default Port:** 8000
- **API Version:** V1 (read-only)
- **Thread Safety:** Dedicated database connection per thread

## Architecture

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| FastAPI Server | `src/webserver/server.py` | REST API endpoints |
| Configuration | `src/webserver/config.py` | Server settings |
| Service Manager | `src/services/web_service_manager.py` | Qt thread wrapper |
| Static Assets | `src/webserver/static/` | Web assets (CSS, JS, images) |
| Templates | `src/webserver/templates/` | HTML templates |

### Threading Model

The webserver runs in a dedicated QThread to avoid blocking the GUI:

```python
# In MainWindow
self.web_service = WebServiceManager(self.db_path)
self.web_thread = QThread()
self.web_service.moveToThread(self.web_thread)
self.web_thread.start()
self.web_service.start_server()
```

**Key Points:**
- ✅ Separate thread prevents UI blocking
- ✅ Dedicated database connection (thread-safe)
- ✅ Graceful shutdown on application exit
- ✅ Proper signal/slot communication with main thread

## Current API Endpoints (V1)

### Health Check

**GET** `/health`

Check if the server is running.

**Response:**
```json
{
  "status": "ok"
}
```

### Longform Document

**GET** `/longform`

Retrieve the entire longform document as HTML.

**Response:**
- **Content-Type:** `text/html`
- **Body:** Rendered HTML document with hierarchical structure

**Features:**
- Server-side rendering of markdown
- Hierarchical document structure preserved
- Parent-child relationships maintained
- Title overrides applied

**Example:**
```bash
curl http://localhost:8000/longform
```

### Future Endpoints (Planned)

V2 API will include full CRUD operations:

- `GET /api/v2/entities` - List entities
- `GET /api/v2/entities/{id}` - Get entity details
- `POST /api/v2/entities` - Create entity
- `PUT /api/v2/entities/{id}` - Update entity
- `DELETE /api/v2/entities/{id}` - Delete entity
- Similar endpoints for events, relations, maps, etc.

## Configuration

### Server Settings

Configuration is managed in `src/webserver/config.py`:

```python
class ServerConfig:
    host: str = "127.0.0.1"  # Localhost only by default
    port: int = 8000
    reload: bool = False      # Hot reload (development only)
```

### Environment Variables

Set these to customize the server:

- `WEBSERVER_HOST` - Server bind address (default: `127.0.0.1`)
- `WEBSERVER_PORT` - Server port (default: `8000`)

**Security Note:** Default binding to `127.0.0.1` ensures the server is only accessible from localhost. For network access, explicitly set `WEBSERVER_HOST=0.0.0.0` (not recommended for production without authentication).

## Usage

### Starting the Server

The server starts automatically when you open a world in the GUI:

1. Launch ProjektKraken
2. Open a world database (.kraken file)
3. Server starts on `http://localhost:8000`

### Accessing the API

**Web Browser:**
```
http://localhost:8000/longform
```

**cURL:**
```bash
# Health check
curl http://localhost:8000/health

# Get longform document
curl http://localhost:8000/longform > world.html
```

**Python:**
```python
import requests

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())  # {"status": "ok"}

# Get longform document
response = requests.get("http://localhost:8000/longform")
html = response.text
```

## Use Cases

### 1. Live Preview

View your longform document in a web browser while editing:

```bash
# Open in browser
xdg-open http://localhost:8000/longform  # Linux
open http://localhost:8000/longform      # macOS
start http://localhost:8000/longform     # Windows
```

### 2. Export to HTML

Save the rendered longform document:

```bash
curl http://localhost:8000/longform > world.html
```

### 3. Integration with External Tools

Access world data from scripts or other applications:

```python
import requests

def get_world_html():
    response = requests.get("http://localhost:8000/longform")
    return response.text

# Use in documentation pipeline
html = get_world_html()
# Process or publish...
```

### 4. Web-Based Viewer

Embed the longform document in a custom web application:

```html
<!DOCTYPE html>
<html>
<head>
    <title>My World</title>
</head>
<body>
    <iframe src="http://localhost:8000/longform" 
            width="100%" height="100%"></iframe>
</body>
</html>
```

## Security Considerations

### Current (V1) Security

⚠️ **Read-Only API:** V1 provides read-only access (no mutations)

✅ **Localhost Binding:** Default binding to `127.0.0.1` prevents network access

✅ **Thread Isolation:** Dedicated database connection prevents race conditions

❌ **No Authentication:** V1 has no authentication (localhost only)

### Future (V2) Security

When CRUD operations are added in V2, the following security measures will be implemented:

- [ ] **Authentication:** API key or JWT-based authentication
- [ ] **Authorization:** Role-based access control (RBAC)
- [ ] **Rate Limiting:** Prevent abuse
- [ ] **CORS:** Configurable cross-origin resource sharing
- [ ] **HTTPS:** Optional TLS/SSL support
- [ ] **Input Validation:** Strict validation of all inputs
- [ ] **Audit Logging:** Track all API operations

### Best Practices

1. **Don't expose to network** without authentication (keep default `127.0.0.1`)
2. **Use reverse proxy** if exposing to network (nginx, Apache)
3. **Add firewall rules** to restrict access
4. **Monitor logs** for suspicious activity
5. **Keep updated** with security patches

## Performance

### Current Performance

- **Latency:** <50ms for health check
- **Latency:** <200ms for longform document (typical)
- **Throughput:** Supports ~100 requests/second (typical workload)

### Optimization Tips

1. **Async Operations:** Server uses async FastAPI for high concurrency
2. **Database Connection:** Dedicated connection per thread (no contention)
3. **Caching:** Consider adding caching for frequently accessed data (future)
4. **Load Balancing:** Not needed for single-user desktop application

## Troubleshooting

### Server Won't Start

**Symptom:** Error message "Address already in use"

**Solution:** Port 8000 is already taken. Change port in configuration or close other application.

```bash
# Check what's using port 8000
lsof -i :8000          # Linux/macOS
netstat -ano | find "8000"  # Windows

# Kill the process or change port
```

### Can't Access from Browser

**Symptom:** Connection refused when accessing `http://localhost:8000`

**Possible Causes:**
1. Server not started (world not open in GUI)
2. Firewall blocking port
3. Using wrong address (should be `localhost` or `127.0.0.1`)

**Solution:**
1. Ensure ProjektKraken is running with a world open
2. Check firewall settings
3. Verify URL is correct

### Slow Response Times

**Symptom:** API requests take >1 second

**Possible Causes:**
1. Large longform document (>10,000 entries)
2. Database locked by GUI operation
3. System resource constraints

**Solution:**
1. Optimize document size
2. Wait for GUI operations to complete
3. Check system resources (CPU, RAM)

## Development

### Running in Development Mode

For development, enable hot reload:

```python
# In src/webserver/config.py
class ServerConfig:
    reload: bool = True  # Enable hot reload
```

**Warning:** Hot reload increases resource usage. Use only during development.

### Adding New Endpoints

1. **Define endpoint in `server.py`:**

```python
@app.get("/api/v2/entities")
async def list_entities():
    # Implementation
    pass
```

2. **Add database access:**

```python
from src.services.db_service import DatabaseService

@app.get("/api/v2/entities")
async def list_entities():
    db = DatabaseService(db_path)
    entities = db.get_all_entities()
    return {"entities": entities}
```

3. **Update documentation** (this file)

4. **Add tests** in `tests/integration/test_webserver.py`

### Testing

Test endpoints using pytest:

```bash
pytest tests/integration/test_webserver.py
```

Or manually with curl:

```bash
# Start ProjektKraken with a world
# Then test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/longform
```

## API Versioning

### Current: V1 (Beta)

- Read-only access
- Basic endpoints (health, longform)
- No authentication
- Localhost only (default)

### Planned: V2 (Future)

- Full CRUD operations
- Authentication and authorization
- Rate limiting
- Comprehensive entity/event/relation endpoints
- WebSocket support for live updates
- GraphQL API (optional)

## Related Documentation

- **[Design.md](../Design.md)** - Architecture specification
- **[DATABASE.md](DATABASE.md)** - Database architecture
- **[QT_THREADING_SAFETY.md](QT_THREADING_SAFETY.md)** - Threading patterns
- **[SECURITY.md](SECURITY.md)** - Security best practices
- **[LONGFORM.md](LONGFORM.md)** - Longform document feature

## Support

For issues or questions:
- Check server logs in application console
- Review threading documentation for integration patterns
- Test with curl before using in application
- Report bugs via GitHub issues

---

**Status:** V1 (Beta) - Read-only API  
**Next Version:** V2 with full CRUD operations (planned)
