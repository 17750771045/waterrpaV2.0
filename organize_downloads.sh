#!/bin/bash
# ============================================================
#  Downloads 目录自动归档脚本
#  用法: bash organize_downloads.sh
# ============================================================

DOWNLOADS_DIR="$HOME/Downloads"

# ---------- 归档规则定义 ----------
declare -A CATEGORY_MAP
# 图片
for ext in jpg jpeg png gif svg webp; do
    CATEGORY_MAP["$ext"]="图片"
done
# 文档
for ext in pdf docx doc xlsx xls pptx ppt md txt csv; do
    CATEGORY_MAP["$ext"]="文档"
done
# 压缩包
for ext in zip rar 7z tar.gz tgz tar.bz2; do
    CATEGORY_MAP["$ext"]="压缩包"
done
# 安装包
for ext in dmg pkg exe msi; do
    CATEGORY_MAP["$ext"]="安装包"
done

# ---------- 统计变量 ----------
declare -A category_files   # category -> "file1 file2 ..."
total_moved=0
total_skipped=0

# ---------- 同名文件处理：追加数字后缀 ----------
get_unique_dest() {
    local dest="$1"
    if [ ! -e "$dest" ]; then
        echo "$dest"
        return
    fi
    local base="${dest%.*}"
    local ext="${dest##*.}"
    local i=1
    while [ -e "${base}_${i}.${ext}" ]; do
        ((i++))
    done
    echo "${base}_${i}.${ext}"
}

# ---------- 遍历文件 ----------
for item in "$DOWNLOADS_DIR"/*; do
    # 跳过不存在的项（空目录时 glob 会保留字面量 *）
    [ -e "$item" ] || continue

    # 跳过隐藏文件
    basename_item="$(basename "$item")"
    [[ "$basename_item" == .* ]] && continue

    # 跳过目录（只处理文件）
    [ -f "$item" ] || continue

    # 跳过已存在的归档子目录本身
    if [[ "$basename_item" == "图片" || "$basename_item" == "文档" || \
          "$basename_item" == "压缩包" || "$basename_item" == "安装包" ]]; then
        continue
    fi

    # 提取扩展名（转小写）
    filename="$basename_item"
    lowercase="${filename,,}"
    ext="${lowercase##*.}"

    # 查找分类
    category="${CATEGORY_MAP[$ext]}"

    if [ -z "$category" ]; then
        ((total_skipped++))
        continue
    fi

    # 创建目标目录
    target_dir="$DOWNLOADS_DIR/$category"
    mkdir -p "$target_dir"

    # 计算目标路径（处理同名）
    dest_path="$(get_unique_dest "$target_dir/$basename_item")"

    # 移动文件
    mv -n "$item" "$dest_path"
    dest_basename="$(basename "$dest_path")"
    category_files["$category"]+="$dest_basename"$'\n'
    ((total_moved++))
done

# ---------- 输出汇总报告 ----------
echo ""
echo "=========================================="
echo "   📦 Downloads 归档整理 — 汇总报告"
echo "=========================================="
echo ""
echo "  ✅ 已归档文件总数: $total_moved"
echo "  ⏭️  跳过文件总数: $total_skipped"
echo ""

for cat in "图片" "文档" "压缩包" "安装包"; do
    files="${category_files[$cat]}"
    if [ -n "$files" ]; then
        count=$(echo -n "$files" | grep -c '^')
        echo "  📂 [$cat] — $count 个文件:"
        echo "$files" | while read -r f; do
            [ -n "$f" ] && echo "       • $f"
        done
        echo ""
    fi
done

echo "=========================================="
echo "  整理完成！"
echo "=========================================="
