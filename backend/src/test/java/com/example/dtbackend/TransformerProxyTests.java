package com.example.dtbackend;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import static org.junit.jupiter.api.Assertions.*;

class TransformerProxyTests {
    @Test void smallOpenSseEventFlushesBeforeUpstreamCloses() throws Exception {
        var flushed=new java.util.concurrent.CountDownLatch(1);
        var observed=new java.util.concurrent.atomic.AtomicBoolean(false);
        HttpServer fake=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        fake.createContext("/api/replay/stream",exchange->{
            exchange.sendResponseHeaders(200,0);
            exchange.getResponseBody().write(": connected\n\n".getBytes(StandardCharsets.UTF_8));exchange.getResponseBody().flush();
            try {observed.set(flushed.await(2,java.util.concurrent.TimeUnit.SECONDS));}
            catch (InterruptedException e) {Thread.currentThread().interrupt();}
            exchange.close();
        });fake.start();
        try {
            var controller=new TransformerController("http://127.0.0.1:"+fake.getAddress().getPort());
            var response=new org.springframework.mock.web.MockHttpServletResponse() { @Override public void flushBuffer() {super.flushBuffer();flushed.countDown();} };
            controller.stream(new MockHttpServletRequest("GET","/api/replay/stream"),response);
            assertTrue(observed.get(),"SSE event was buffered until the open upstream closed");
            assertEquals(": connected\n\n",response.getContentAsString());
        } finally {fake.stop(0);}
    }
    @Test void relaysExactWorkerBodyAndQuery() throws Exception {
        HttpServer fake=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        fake.createContext("/api/transformers/current",exchange->{
            assertEquals("sessionId=abc",exchange.getRequestURI().getQuery());
            byte[] body="{\"ml\":{\"thermalAlert\":null,\"thermalScore\":13.297415516625}}".getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200,body.length);exchange.getResponseBody().write(body);exchange.close();
        });fake.start();
        try {
            var controller=new TransformerController("http://127.0.0.1:"+fake.getAddress().getPort());
            var request=new MockHttpServletRequest("GET","/api/transformers/current");request.setQueryString("sessionId=abc");
            var response=controller.route(request,null);
            assertEquals(200,response.getStatusCode().value());
            assertEquals("{\"ml\":{\"thermalAlert\":null,\"thermalScore\":13.297415516625}}",new String(response.getBody(),StandardCharsets.UTF_8));
            assertEquals("no-store",response.getHeaders().getFirst("Cache-Control"));
        } finally {fake.stop(0);}
    }
    @Test void unknownRoutesRejectedAndWorkerFailureExplicit() {
        var controller=new TransformerController("http://127.0.0.1:1");
        assertEquals(404,controller.route(new MockHttpServletRequest("GET","/api/private"),null).getStatusCode().value());
        assertEquals(503,controller.route(new MockHttpServletRequest("GET","/api/health"),null).getStatusCode().value());
    }
    @Test void nonLoopbackWorkerRejected() {
        assertThrows(IllegalArgumentException.class,()->new TransformerController("http://example.com:8765"));
    }
}
