#!/bin/bash
# Demo: Chạy MCP server trực tiếp từ Docker image (không cần cài đặt)

echo "🚀 Starting PromptQL MCP Server from Docker image..."
echo "📦 Image size: 159MB (self-contained với tất cả dependencies)"
echo ""
echo "✅ Không cần cài đặt:"
echo "   - Python"
echo "   - pip packages"
echo "   - Dependencies"
echo ""
echo "📋 Chỉ cần:"
echo "   - Docker"
echo "   - File .env với credentials"
echo ""

# Test với docker run trực tiếp
echo "=== TEST 1: Docker Run (Interactive Mode) ==="
timeout 3 docker run --rm -i --env-file .env prompt-graphql-server:local <<EOF
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"0.1.0","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
EOF

echo ""
echo "=== TEST 2: Docker Compose ==="
echo "Config trong docker-compose.yml:"
cat docker-compose.yml | grep -A 10 "prompt-graphql-server:" | head -12

echo ""
echo "✅ Image đã sẵn sàng sử dụng!"
echo ""
echo "📝 Cách sử dụng:"
echo "   1. Có file .env với credentials"
echo "   2. docker-compose up -d"
echo "   3. Hoặc: docker run --rm -i --env-file .env prompt-graphql-server:local"
