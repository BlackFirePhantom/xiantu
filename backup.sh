#!/bin/bash
# 仙途数据库备份脚本
# 用法: ./backup.sh [备份目录]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
BACKUP_DIR="${1:-${SCRIPT_DIR}/backups}"
DB_FILE="${DATA_DIR}/game.db"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/game_${TIMESTAMP}.db"

if [ ! -f "$DB_FILE" ]; then
    echo "错误: 数据库文件不存在: $DB_FILE"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

# 使用 SQLite 的 .backup 命令确保数据一致性
sqlite3 "$DB_FILE" ".backup '${BACKUP_FILE}'"

# 压缩备份
gzip "$BACKUP_FILE"

echo "备份完成: ${BACKUP_FILE}.gz"

# 清理 30 天前的备份
find "$BACKUP_DIR" -name "game_*.db.gz" -mtime +30 -delete
echo "已清理 30 天前的备份"
