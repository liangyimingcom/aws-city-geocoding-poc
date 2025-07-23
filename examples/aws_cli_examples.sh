#!/bin/bash

# AWS CLI地理编码示例
# 使用Profile: oversea1, Region: us-west-2

echo "=== AWS Location Service CLI示例 ==="

# 1. 创建Place Index
echo "1. 创建Place Index..."
aws location create-place-index \
    --index-name "CityGeocodingIndex" \
    --data-source "Esri" \
    --description "城市地理编码索引" \
    --pricing-plan "RequestBasedUsage" \
    --profile oversea1 \
    --region us-west-2

# 2. 等待Place Index创建完成
echo "2. 等待Place Index创建完成..."
sleep 30

# 3. 查询中文城市
echo "3. 查询北京..."
aws location search-place-index-for-text \
    --index-name "CityGeocodingIndex" \
    --text "北京, 中国" \
    --language "zh-CN" \
    --max-results 1 \
    --profile oversea1 \
    --region us-west-2

echo ""
echo "4. 查询上海..."
aws location search-place-index-for-text \
    --index-name "CityGeocodingIndex" \
    --text "上海, 中国" \
    --language "zh-CN" \
    --max-results 1 \
    --profile oversea1 \
    --region us-west-2

# 5. 查询英文城市
echo ""
echo "5. 查询纽约..."
aws location search-place-index-for-text \
    --index-name "CityGeocodingIndex" \
    --text "New York, United States" \
    --language "en" \
    --max-results 1 \
    --profile oversea1 \
    --region us-west-2

# 6. 反向地理编码
echo ""
echo "6. 反向地理编码（北京坐标）..."
aws location search-place-index-for-position \
    --index-name "CityGeocodingIndex" \
    --position "[116.3912757,39.906217001]" \
    --language "zh-CN" \
    --max-results 1 \
    --profile oversea1 \
    --region us-west-2

# 7. 查看Place Index信息
echo ""
echo "7. 查看Place Index信息..."
aws location describe-place-index \
    --index-name "CityGeocodingIndex" \
    --profile oversea1 \
    --region us-west-2

# 8. 清理资源（可选）
echo ""
read -p "是否删除Place Index以避免费用? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "删除Place Index..."
    aws location delete-place-index \
        --index-name "CityGeocodingIndex" \
        --profile oversea1 \
        --region us-west-2
    echo "Place Index已删除"
else
    echo "保留Place Index，请注意可能产生的费用"
fi

echo "示例完成！"
