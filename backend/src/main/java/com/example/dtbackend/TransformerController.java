package com.example.dtbackend;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;

/** Existing Spring Boot API, now connecting to one persistent loopback Python worker. */
@RestController
public class TransformerController {
    private static final int MAX_BYTES=100*1024*1024;
    private static final Set<String> GET_ROUTES=Set.of("/api/health","/api/datasets/local","/api/datasets/status",
      "/api/replay/status","/api/transformers/current","/api/transformer/current","/api/transformers/history",
      "/api/transformers/alerts","/api/transformers/maintenance",
      "/api/summary/overall","/api/summary/thermal","/api/summary/electrical","/api/summary/data-quality","/api/summary/model","/api/summary/recurrence","/api/summary/thermal-dna","/api/summary/maintenance","/api/summary/export",
      "/api/intelligence/evidence","/api/intelligence/maintenance","/api/intelligence/dna");
    private static final Set<String> POST_ROUTES=Set.of("/api/replay/local/start","/api/datasets/upload","/api/replay/uploaded/start",
      "/api/replay/play","/api/replay/pause","/api/replay/resume","/api/replay/restart","/api/replay/stop","/api/replay/speed","/api/replay/cancel","/api/datasets/delete",
      "/api/intelligence/simulate","/api/intelligence/maintenance","/api/intelligence/dna/reference");
    private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    private final String worker;
    public TransformerController(@Value("${voltmind.worker-url:http://127.0.0.1:8765}") String worker) {
        if (!worker.matches("http://127\\.0\\.0\\.1:[0-9]+")) throw new IllegalArgumentException("Worker must be a loopback HTTP service");
        this.worker=worker;
    }
    private URI uri(HttpServletRequest request) {
        return URI.create(worker+request.getRequestURI()+(request.getQueryString()==null?"":"?"+request.getQueryString()));
    }
    private ResponseEntity<byte[]> error(int code,String message) {
        return ResponseEntity.status(code).contentType(MediaType.APPLICATION_JSON).body(("{\"status\":\"FAILED\",\"error\":\""+message+"\"}").getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
    @RequestMapping(path="/api/**",method={RequestMethod.GET,RequestMethod.POST})
    public ResponseEntity<byte[]> route(HttpServletRequest request,@RequestBody(required=false) byte[] body) {
        String path=request.getRequestURI();String method=request.getMethod();
        if (!(method.equals("GET")?GET_ROUTES:POST_ROUTES).contains(path)) return error(404,"Unknown API route");
        if (body!=null && body.length>MAX_BYTES) return error(413,"Upload/request exceeds 100 MiB limit");
        try {
            HttpRequest.Builder builder=HttpRequest.newBuilder(uri(request)).timeout(Duration.ofSeconds(120));
            if (method.equals("POST")) {
                builder.POST(HttpRequest.BodyPublishers.ofByteArray(body==null?new byte[0]:body));
                builder.header("Content-Type",request.getContentType()==null?"application/json":request.getContentType());
            } else builder.GET();
            HttpResponse<byte[]> response=client.send(builder.build(),HttpResponse.BodyHandlers.ofByteArray());
            return ResponseEntity.status(response.statusCode()).header(HttpHeaders.CONTENT_TYPE,"application/json; charset=utf-8")
                    .header(HttpHeaders.CACHE_CONTROL,"no-store").body(response.body());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();return error(503,"Backend request interrupted");
        } catch (IOException e) { return error(503,"ML worker unavailable. Start all services using start_voltmind.bat and check .state service logs."); }
    }
    @GetMapping("/api/replay/stream")
    public void stream(HttpServletRequest request,jakarta.servlet.http.HttpServletResponse downstream) throws IOException {
        java.net.HttpURLConnection upstream=(java.net.HttpURLConnection)uri(request).toURL().openConnection();
        upstream.setConnectTimeout(5000);upstream.setReadTimeout(10000);upstream.setUseCaches(false);
        if (request.getHeader("Last-Event-ID")!=null) upstream.setRequestProperty("Last-Event-ID",request.getHeader("Last-Event-ID"));
        try {
            int status=upstream.getResponseCode();
            downstream.setStatus(status);downstream.setContentType(status==200?"text/event-stream":"application/json");
            downstream.setCharacterEncoding("UTF-8");downstream.setHeader("Cache-Control","no-store");downstream.setHeader("X-Accel-Buffering","no");
            // Commit headers explicitly; servlet streaming must not wait for a full buffer or upstream EOF.
            downstream.flushBuffer();
            InputStream body=status>=400?upstream.getErrorStream():upstream.getInputStream();
            if (body==null)return;
            try (InputStream input=new java.io.BufferedInputStream(body)) {
                var output=downstream.getOutputStream();var event=new java.io.ByteArrayOutputStream();int value,previous=-1;
                while ((value=input.read())!=-1) {
                    event.write(value);
                    if ((value=='\n' && previous=='\n') || event.size()>=65536) {
                        event.writeTo(output);event.reset();downstream.flushBuffer();
                    }
                    previous=value;
                }
                if (event.size()>0) {event.writeTo(output);downstream.flushBuffer();}
            }
        } catch (IOException disconnect) {
            if (!downstream.isCommitted()) {
                downstream.setStatus(503);downstream.setContentType("application/json");
                downstream.getOutputStream().write("{\"error\":\"ML worker unavailable\"}".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                downstream.flushBuffer();
            }
        } finally {upstream.disconnect();}
    }
}
