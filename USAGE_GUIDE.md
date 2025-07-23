# Amazon Location Service 使用指南

## 快速开始

### 1. 环境准备

```bash
# 确保AWS CLI已配置
aws configure --profile oversea1

# 验证配置
aws sts get-caller-identity --profile oversea1 --region us-west-2
```

### 2. 创建Place Index

```bash
# 创建Place Index
aws location create-place-index \
    --index-name "CityGeocodingIndex" \
    --data-source "Esri" \
    --description "城市地理编码索引" \
    --pricing-plan "RequestBasedUsage" \
    --profile oversea1 \
    --region us-west-2

# 检查创建状态
aws location describe-place-index \
    --index-name "CityGeocodingIndex" \
    --profile oversea1 \
    --region us-west-2
```

### 3. 基础API调用

#### 3.1 正向地理编码（城市名称 → 坐标）

```bash
# 查询中文城市
aws location search-place-index-for-text \
    --index-name "CityGeocodingIndex" \
    --text "北京, 中国" \
    --language "zh-CN" \
    --max-results 1 \
    --profile oversea1 \
    --region us-west-2

# 查询英文城市
aws location search-place-index-for-text \
    --index-name "CityGeocodingIndex" \
    --text "New York, United States" \
    --language "en" \
    --max-results 1 \
    --profile oversea1 \
    --region us-west-2
```

#### 3.2 反向地理编码（坐标 → 地址）

```bash
# 根据坐标查询地址
aws location search-place-index-for-position \
    --index-name "CityGeocodingIndex" \
    --position "[116.3912757,39.906217001]" \
    --language "zh-CN" \
    --max-results 1 \
    --profile oversea1 \
    --region us-west-2
```

## Python代码示例

### 1. 使用boto3库

```python
import boto3

# 创建客户端
session = boto3.Session(profile_name='oversea1')
location_client = session.client('location', region_name='us-west-2')

# 正向地理编码
def geocode_city(city_name, country=None):
    query_text = f"{city_name}, {country}" if country else city_name
    
    response = location_client.search_place_index_for_text(
        IndexName='CityGeocodingIndex',
        Text=query_text,
        MaxResults=1,
        Language='zh-CN'
    )
    
    if response['Results']:
        result = response['Results'][0]
        place = result['Place']
        geometry = place['Geometry']['Point']
        
        return {
            'success': True,
            'city': city_name,
            'latitude': geometry[1],  # 注意：Location Service返回[lon, lat]
            'longitude': geometry[0],
            'address': place.get('Label'),
            'relevance': result.get('Relevance')
        }
    else:
        return {'success': False, 'error': '未找到城市'}

# 使用示例
result = geocode_city("北京", "中国")
print(f"北京坐标: ({result['latitude']}, {result['longitude']})")
```

### 2. 使用AWS CLI (subprocess)

```python
import subprocess
import json

def geocode_with_cli(city_name, country=None):
    query_text = f"{city_name}, {country}" if country else city_name
    
    cmd = [
        'aws', 'location', 'search-place-index-for-text',
        '--index-name', 'CityGeocodingIndex',
        '--text', query_text,
        '--language', 'zh-CN',
        '--max-results', '1',
        '--profile', 'oversea1',
        '--region', 'us-west-2'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        data = json.loads(result.stdout)
        if data['Results']:
            place = data['Results'][0]['Place']
            geometry = place['Geometry']['Point']
            
            return {
                'success': True,
                'latitude': geometry[1],
                'longitude': geometry[0],
                'address': place.get('Label')
            }
    
    return {'success': False, 'error': '查询失败'}

# 使用示例
result = geocode_with_cli("上海", "中国")
print(f"上海坐标: ({result['latitude']}, {result['longitude']})")
```

## 高级功能

### 1. 批量地理编码

```python
import time

def batch_geocode(cities, delay=1.0):
    """批量地理编码，避免请求过于频繁"""
    results = []
    
    for city, country in cities:
        result = geocode_city(city, country)
        results.append(result)
        
        # 避免请求过于频繁
        time.sleep(delay)
    
    return results

# 使用示例
cities = [
    ("北京", "中国"),
    ("上海", "中国"),
    ("深圳", "中国")
]

batch_results = batch_geocode(cities)
for result in batch_results:
    if result['success']:
        print(f"{result['city']}: ({result['latitude']}, {result['longitude']})")
```

### 2. 错误处理和重试

```python
import time
from botocore.exceptions import ClientError

def robust_geocode(city_name, country=None, max_retries=3):
    """带重试机制的地理编码"""
    
    for attempt in range(max_retries):
        try:
            result = geocode_city(city_name, country)
            if result['success']:
                return result
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ThrottlingException':
                # 请求过于频繁，等待后重试
                wait_time = (2 ** attempt) * 1  # 指数退避
                print(f"请求过于频繁，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"API错误: {error_code}")
                break
        except Exception as e:
            print(f"未知错误: {e}")
            break
    
    return {'success': False, 'error': f'经过 {max_retries} 次尝试后仍然失败'}
```

### 3. 结果缓存

```python
import json
import os
from datetime import datetime, timedelta

class GeocodingCache:
    def __init__(self, cache_file='geocoding_cache.json', expire_hours=24):
        self.cache_file = cache_file
        self.expire_hours = expire_hours
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """加载缓存文件"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """保存缓存到文件"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
    
    def _is_expired(self, timestamp):
        """检查缓存是否过期"""
        cache_time = datetime.fromisoformat(timestamp)
        expire_time = cache_time + timedelta(hours=self.expire_hours)
        return datetime.now() > expire_time
    
    def get(self, city_name, country=None):
        """从缓存获取结果"""
        cache_key = f"{city_name}_{country or 'None'}"
        
        if cache_key in self.cache:
            cached_item = self.cache[cache_key]
            if not self._is_expired(cached_item['timestamp']):
                print(f"从缓存获取: {city_name}")
                return cached_item['result']
            else:
                # 缓存过期，删除
                del self.cache[cache_key]
        
        return None
    
    def set(self, city_name, country, result):
        """保存结果到缓存"""
        cache_key = f"{city_name}_{country or 'None'}"
        
        self.cache[cache_key] = {
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
        
        self._save_cache()

# 使用缓存的地理编码函数
def cached_geocode(city_name, country=None):
    cache = GeocodingCache()
    
    # 先尝试从缓存获取
    cached_result = cache.get(city_name, country)
    if cached_result:
        return cached_result
    
    # 缓存未命中，调用API
    print(f"API查询: {city_name}")
    result = geocode_city(city_name, country)
    
    # 保存成功结果到缓存
    if result['success']:
        cache.set(city_name, country, result)
    
    return result
```

## 监控和成本控制

### 1. 设置CloudWatch告警

```bash
# 创建成本告警
aws cloudwatch put-metric-alarm \
    --alarm-name "LocationService-HighUsage" \
    --alarm-description "Location Service使用量过高" \
    --metric-name "RequestCount" \
    --namespace "AWS/Location" \
    --statistic "Sum" \
    --period 3600 \
    --threshold 1000 \
    --comparison-operator "GreaterThanThreshold" \
    --evaluation-periods 1 \
    --profile oversea1 \
    --region us-west-2
```

### 2. 查看使用统计

```bash
# 查看Place Index使用统计
aws logs filter-log-events \
    --log-group-name "/aws/location/place-index" \
    --start-time $(date -d '1 day ago' +%s)000 \
    --profile oversea1 \
    --region us-west-2
```

### 3. 成本优化建议

```python
# 实现请求频率限制
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, max_requests_per_minute=60):
        self.max_requests = max_requests_per_minute
        self.requests = defaultdict(list)
    
    def can_make_request(self, key="default"):
        now = time.time()
        minute_ago = now - 60
        
        # 清理过期的请求记录
        self.requests[key] = [
            req_time for req_time in self.requests[key] 
            if req_time > minute_ago
        ]
        
        # 检查是否超过限制
        if len(self.requests[key]) >= self.max_requests:
            return False
        
        # 记录当前请求
        self.requests[key].append(now)
        return True
    
    def wait_if_needed(self, key="default"):
        if not self.can_make_request(key):
            wait_time = 60 - (time.time() - min(self.requests[key]))
            print(f"请求频率限制，等待 {wait_time:.1f} 秒...")
            time.sleep(wait_time)

# 使用频率限制的地理编码
rate_limiter = RateLimiter(max_requests_per_minute=30)

def rate_limited_geocode(city_name, country=None):
    rate_limiter.wait_if_needed()
    return geocode_city(city_name, country)
```

## 清理资源

### 删除Place Index

```bash
# 删除Place Index
aws location delete-place-index \
    --index-name "CityGeocodingIndex" \
    --profile oversea1 \
    --region us-west-2

# 确认删除
aws location list-place-indexes \
    --profile oversea1 \
    --region us-west-2
```

## 故障排除

### 常见错误及解决方案

#### 1. ResourceNotFoundException
```
错误: Place Index不存在
解决: 确保已创建Place Index，检查名称是否正确
```

#### 2. AccessDeniedException
```
错误: 权限不足
解决: 检查IAM权限，确保有location:*权限
```

#### 3. ThrottlingException
```
错误: 请求过于频繁
解决: 实现请求频率限制，增加请求间隔
```

#### 4. ValidationException
```
错误: 参数验证失败
解决: 检查参数格式，特别是坐标格式[经度, 纬度]
```

### 调试技巧

```python
import logging

# 启用boto3调试日志
logging.basicConfig(level=logging.DEBUG)
boto3.set_stream_logger('boto3', logging.DEBUG)
boto3.set_stream_logger('botocore', logging.DEBUG)

# 或者只记录错误
logging.basicConfig(level=logging.ERROR)
```

## 最佳实践总结

1. **权限管理**: 使用最小权限原则，只授予必要的Location Service权限
2. **成本控制**: 实现缓存和频率限制，避免不必要的API调用
3. **错误处理**: 实现完善的错误处理和重试机制
4. **监控告警**: 设置使用量和成本告警
5. **数据验证**: 验证输入数据，避免无效查询
6. **性能优化**: 使用批量处理和异步调用提高效率
7. **安全考虑**: 不要在客户端直接暴露AWS凭证

---

**注意**: 使用Amazon Location Service会产生费用，请根据实际需求合理使用，并及时清理不需要的资源。
