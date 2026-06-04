# Docker 编排说明

## 启动 / 停止

```bash
# 复制环境变量模板（首次）
cp .env.example .env

# 启动 MySQL
docker compose up -d mysql

# 停止
docker compose down
```

## 查看 MySQL 日志

```bash
docker compose logs -f mysql
```

## 进入 MySQL CLI

```bash
docker compose exec mysql mysql -uroot -p${MYSQL_ROOT_PASSWORD} distiller_hub
```

## 重置数据卷（开发期重置 schema）

```bash
docker compose down -v
docker volume rm distiller-mysql-data
docker compose up -d mysql
```

## 健康检查

```bash
docker compose ps
```

## 注意

- 生产部署不在本期范围
- 初始化脚本放在 `./docker/mysql/`，仅首次空卷启动时执行
- 数据卷使用 Docker named volume `distiller-mysql-data`，避免 Windows 绑定挂载性能问题
