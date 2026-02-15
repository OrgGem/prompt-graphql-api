# 🚀 Quick Start Guide - Sử dụng Docker Image

## ✅ Không cần cài đặt gì thêm!

Image `prompt-graphql-server:local` đã **self-contained** với:
- ✅ Python 3.12
- ✅ Tất cả dependencies (mcp, requests, python-dotenv)
- ✅ PromptQL MCP Server code
- ✅ Size: 159MB

## 📋 Yêu cầu tối thiểu

Chỉ cần:
1. **Docker** đã cài đặt
2. **File `.env`** với credentials

## 🎯 Cách 1: Docker Compose (Khuyến nghị)

### Bước 1: Tạo/Cập nhật file `.env`

```bash
cat > .env << 'EOF'
# PromptQL Credentials
PROMPTQL_API_KEY=your_api_key_here
PROMPTQL_PLAYGROUND_URL=https://promptql.your-project.hasura.app/playground
PROMPTQL_AUTH_TOKEN=your_auth_token_here
PROMPTQL_AUTH_MODE=public

# Optional: Hasura CE endpoint
PROMPTQL_HASURA_GRAPHQL_ENDPOINT=http://hasura:8080/v1/graphql
PROMPTQL_HASURA_ADMIN_SECRET=your_admin_secret
EOF
```

### Bước 2: Start server

```bash
# Chỉ MCP server
docker-compose up -d prompt-graphql-server

# Hoặc full stack (MCP + Hasura + Postgres)
docker-compose --profile sample-hasura up -d
```

### Bước 3: Kiểm tra

```bash
docker ps
docker logs prompt-graphql-server
```

## 🎯 Cách 2: Docker Run trực tiếp

```bash
# Interactive mode (cho MCP client kết nối qua stdio)
docker run --rm -i --env-file .env prompt-graphql-server:local

# Hoặc với specific env vars
docker run --rm -i \
  -e PROMPTQL_API_KEY=your_key \
  -e PROMPTQL_PLAYGROUND_URL=https://... \
  -e PROMPTQL_AUTH_TOKEN=your_token \
  -e PROMPTQL_AUTH_MODE=public \
  prompt-graphql-server:local
```

## 🧪 Test nhanh

```bash
# Test với Python client
python test_docker.py

# Hoặc test với example client
python examples/simple_client.py
```

## 📦 Export/Import Image (Để triển khai máy khác)

### Export image

```bash
# Lưu image thành file tar
docker save prompt-graphql-server:local | gzip > promptql-mcp-server.tar.gz

# Kích thước file: ~55MB (nén từ 159MB)
```

### Import trên máy khác

```bash
# Load image
docker load < promptql-mcp-server.tar.gz

# Hoặc từ gzip
gunzip -c promptql-mcp-server.tar.gz | docker load

# Kiểm tra
docker images | grep prompt-graphql-server
```

### Sử dụng ngay

```bash
# Copy file .env sang máy mới
# Chạy ngay
docker-compose up -d prompt-graphql-server
```

## 🔧 Các lệnh hữu ích

```bash
# Xem logs real-time
docker logs -f prompt-graphql-server

# Stop server
docker-compose down

# Restart
docker-compose restart prompt-graphql-server

# Kiểm tra container status
docker ps -a | grep prompt-graphql-server

# Vào trong container (debug)
docker exec -it prompt-graphql-server /bin/bash
```

## 🎓 MCP Tools Available

Sau khi start, bạn có 9 tools:

1. **setup_config** - Cấu hình credentials
2. **check_config** - Kiểm tra config  
3. **start_thread** - Bắt đầu conversation
4. **continue_thread** - Tiếp tục thread
5. **get_thread_status** - Xem trạng thái
6. **cancel_thread** - Hủy thread
7. **get_artifact** - Lấy artifacts
8. **start_thread_without_polling** - Async start
9. **query_hasura_ce** - Query Hasura CE v2

## 💡 Lưu ý

- **MCP Server** chạy ở stdio mode nên cần MCP client kết nối
- Container **restart** là bình thường khi chạy detached
- Khi có client kết nối (Claude Desktop, test script), server hoạt động bình thường
- **Không cần cài Python hay package nào** trên máy host!

## 🚢 Deploy lên Production

```bash
# 1. Tag image với version
docker tag prompt-graphql-server:local prompt-graphql-server:v1.0.0

# 2. Push lên registry (nếu có)
docker tag prompt-graphql-server:local your-registry/promptql-mcp:v1.0.0
docker push your-registry/promptql-mcp:v1.0.0

# 3. Sử dụng trên server khác
docker pull your-registry/promptql-mcp:v1.0.0
docker run --env-file .env your-registry/promptql-mcp:v1.0.0
```

## ✅ Tóm tắt

**Image đã build = Sẵn sàng sử dụng!**

- ❌ Không cần: cài Python, pip install, setup môi trường
- ✅ Chỉ cần: Docker + file .env
- 🚀 Chạy ngay: `docker-compose up -d`
