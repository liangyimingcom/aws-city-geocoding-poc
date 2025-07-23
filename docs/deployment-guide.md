# Amazon Location Service 部署指南

## 概述

本指南提供了Amazon Location Service城市地理编码解决方案的详细部署步骤，包括环境准备、资源配置、部署流程和运维监控。

## 环境准备

### 1. AWS CLI配置

```bash
# 安装AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# 配置AWS凭证
aws configure --profile oversea1
# AWS Access Key ID: [Your Access Key]
# AWS Secret Access Key: [Your Secret Key]
# Default region name: us-west-2
# Default output format: json

# 验证配置
aws sts get-caller-identity --profile oversea1 --region us-west-2
```

### 2. 开发环境设置

```bash
# Python环境
python3 -m venv location-service-env
source location-service-env/bin/activate
pip install -r requirements.txt

# 验证boto3安装
python3 -c "import boto3; print('boto3 version:', boto3.__version__)"
```

### 3. 权限配置

创建IAM策略和角色：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "geo:CreatePlaceIndex",
        "geo:DescribePlaceIndex",
        "geo:DeletePlaceIndex",
        "geo:ListPlaceIndexes",
        "geo:SearchPlaceIndexForText",
        "geo:SearchPlaceIndexForPosition"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## 基础部署

### 1. 创建Place Index

#### 使用AWS CLI
```bash
# 创建Place Index
aws location create-place-index \
    --index-name "CityGeocodingIndex" \
    --data-source "Esri" \
    --description "城市地理编码索引" \
    --pricing-plan "RequestBasedUsage" \
    --profile oversea1 \
    --region us-west-2

# 等待创建完成
aws location describe-place-index \
    --index-name "CityGeocodingIndex" \
    --profile oversea1 \
    --region us-west-2
```

#### 使用Python脚本
```bash
# 运行自动化设置脚本
python3 setup_location_service.py
```

### 2. 测试基础功能

```bash
# 运行基础测试
python3 location_service_cli_poc.py

# 或使用boto3版本
python3 location_service_poc.py
```

## Lambda部署

### 1. 创建部署包

```bash
# 创建部署目录
mkdir lambda-deployment
cd lambda-deployment

# 复制代码文件
cp ../location_service_poc.py .
cp ../requirements.txt .

# 安装依赖到部署包
pip install -r requirements.txt -t .

# 创建部署包
zip -r ../location-service-deployment.zip .
cd ..
```

### 2. 创建Lambda函数

```bash
# 创建Lambda函数
aws lambda create-function \
    --function-name city-geocoding-location-service \
    --runtime python3.9 \
    --role arn:aws:iam::ACCOUNT_ID:role/location-service-lambda-role \
    --handler location_service_poc.lambda_handler \
    --zip-file fileb://location-service-deployment.zip \
    --timeout 30 \
    --memory-size 256 \
    --environment Variables='{PLACE_INDEX_NAME=CityGeocodingIndex}' \
    --profile oversea1 \
    --region us-west-2

# 测试Lambda函数
aws lambda invoke \
    --function-name city-geocoding-location-service \
    --payload '{"city": "北京", "country": "中国"}' \
    --profile oversea1 \
    --region us-west-2 \
    response.json

cat response.json
```

## API Gateway部署

### 1. 创建REST API

```bash
# 创建REST API
API_ID=$(aws apigateway create-rest-api \
    --name "location-service-geocoding-api" \
    --description "Amazon Location Service地理编码API" \
    --profile oversea1 \
    --region us-west-2 \
    --query 'id' --output text)

echo "API ID: $API_ID"

# 获取根资源ID
ROOT_ID=$(aws apigateway get-resources \
    --rest-api-id $API_ID \
    --profile oversea1 \
    --region us-west-2 \
    --query 'items[0].id' --output text)

# 创建geocode资源
RESOURCE_ID=$(aws apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $ROOT_ID \
    --path-part "geocode" \
    --profile oversea1 \
    --region us-west-2 \
    --query 'id' --output text)
```

### 2. 配置POST方法

```bash
# 创建POST方法
aws apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method POST \
    --authorization-type NONE \
    --profile oversea1 \
    --region us-west-2

# 设置Lambda集成
ACCOUNT_ID=$(aws sts get-caller-identity --profile oversea1 --query Account --output text)

aws apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $RESOURCE_ID \
    --http-method POST \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:us-west-2:lambda:path/2015-03-31/functions/arn:aws:lambda:us-west-2:$ACCOUNT_ID:function:city-geocoding-location-service/invocations" \
    --profile oversea1 \
    --region us-west-2

# 添加Lambda权限
aws lambda add-permission \
    --function-name city-geocoding-location-service \
    --statement-id api-gateway-invoke \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:us-west-2:$ACCOUNT_ID:$API_ID/*/*" \
    --profile oversea1 \
    --region us-west-2
```

### 3. 部署API

```bash
# 部署到prod阶段
aws apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name prod \
    --profile oversea1 \
    --region us-west-2

# 获取API端点
echo "API端点: https://$API_ID.execute-api.us-west-2.amazonaws.com/prod/geocode"
```

### 4. 测试API

```bash
# 测试API调用
curl -X POST https://$API_ID.execute-api.us-west-2.amazonaws.com/prod/geocode \
  -H 'Content-Type: application/json' \
  -d '{"city": "北京", "country": "中国"}'

# 测试英文城市
curl -X POST https://$API_ID.execute-api.us-west-2.amazonaws.com/prod/geocode \
  -H 'Content-Type: application/json' \
  -d '{"city": "New York", "country": "United States"}'
```

## 企业级部署

### 1. CloudFormation模板部署

创建 `location-service-stack.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Amazon Location Service城市地理编码解决方案'

Parameters:
  PlaceIndexName:
    Type: String
    Default: CityGeocodingIndex
    Description: Place Index名称
  
  DataSource:
    Type: String
    Default: Esri
    AllowedValues: [Esri, Here, Grab]
    Description: 地图数据源

Resources:
  # Place Index
  PlaceIndex:
    Type: AWS::Location::PlaceIndex
    Properties:
      IndexName: !Ref PlaceIndexName
      DataSource: !Ref DataSource
      PricingPlan: RequestBasedUsage
      Description: 城市地理编码Place Index
      Tags:
        - Key: Environment
          Value: Production
        - Key: Application
          Value: CityGeocoding

  # Lambda执行角色
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: LocationServiceAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - geo:SearchPlaceIndexForText
                  - geo:SearchPlaceIndexForPosition
                Resource: !GetAtt PlaceIndex.IndexArn

  # Lambda函数
  GeocodingFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: city-geocoding-location-service
      Runtime: python3.9
      Handler: location_service_poc.lambda_handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        ZipFile: |
          # 这里应该包含实际的Lambda代码
          def lambda_handler(event, context):
              return {'statusCode': 200, 'body': 'Hello World'}
      Environment:
        Variables:
          PLACE_INDEX_NAME: !Ref PlaceIndex
      Timeout: 30
      MemorySize: 256

  # API Gateway
  RestApi:
    Type: AWS::ApiGateway::RestApi
    Properties:
      Name: location-service-geocoding-api
      Description: Amazon Location Service地理编码API
      EndpointConfiguration:
        Types:
          - REGIONAL

  # API Gateway资源和方法
  GeocodeResource:
    Type: AWS::ApiGateway::Resource
    Properties:
      RestApiId: !Ref RestApi
      ParentId: !GetAtt RestApi.RootResourceId
      PathPart: geocode

  GeocodeMethod:
    Type: AWS::ApiGateway::Method
    Properties:
      RestApiId: !Ref RestApi
      ResourceId: !Ref GeocodeResource
      HttpMethod: POST
      AuthorizationType: NONE
      Integration:
        Type: AWS_PROXY
        IntegrationHttpMethod: POST
        Uri: !Sub 'arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${GeocodingFunction.Arn}/invocations'

  # Lambda权限
  LambdaPermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref GeocodingFunction
      Action: lambda:InvokeFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub '${RestApi}/*/POST/geocode'

  # API部署
  ApiDeployment:
    Type: AWS::ApiGateway::Deployment
    DependsOn: GeocodeMethod
    Properties:
      RestApiId: !Ref RestApi
      StageName: prod

Outputs:
  PlaceIndexArn:
    Description: Place Index ARN
    Value: !GetAtt PlaceIndex.IndexArn
  
  ApiEndpoint:
    Description: API Gateway端点
    Value: !Sub 'https://${RestApi}.execute-api.${AWS::Region}.amazonaws.com/prod/geocode'
  
  LambdaFunctionArn:
    Description: Lambda函数ARN
    Value: !GetAtt GeocodingFunction.Arn
```

部署CloudFormation栈：

```bash
# 部署CloudFormation栈
aws cloudformation deploy \
    --template-file location-service-stack.yaml \
    --stack-name location-service-geocoding \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides PlaceIndexName=CityGeocodingIndex DataSource=Esri \
    --profile oversea1 \
    --region us-west-2

# 获取输出
aws cloudformation describe-stacks \
    --stack-name location-service-geocoding \
    --profile oversea1 \
    --region us-west-2 \
    --query 'Stacks[0].Outputs'
```

### 2. 监控和告警配置

```bash
# 创建CloudWatch告警
aws cloudwatch put-metric-alarm \
    --alarm-name "LocationService-HighErrorRate" \
    --alarm-description "Location Service错误率过高" \
    --metric-name "Errors" \
    --namespace "AWS/Lambda" \
    --statistic "Sum" \
    --period 300 \
    --threshold 10 \
    --comparison-operator "GreaterThanThreshold" \
    --dimensions Name=FunctionName,Value=city-geocoding-location-service \
    --evaluation-periods 2 \
    --profile oversea1 \
    --region us-west-2

# 创建成本告警
aws budgets create-budget \
    --account-id $(aws sts get-caller-identity --profile oversea1 --query Account --output text) \
    --budget '{
        "BudgetName": "LocationServiceBudget",
        "BudgetLimit": {
            "Amount": "100",
            "Unit": "USD"
        },
        "TimeUnit": "MONTHLY",
        "BudgetType": "COST",
        "CostFilters": {
            "Service": ["Amazon Location Service"]
        }
    }' \
    --profile oversea1
```

## 性能优化部署

### 1. 缓存层部署

```bash
# 创建ElastiCache子网组
aws elasticache create-cache-subnet-group \
    --cache-subnet-group-name location-service-cache-subnet \
    --cache-subnet-group-description "Location Service缓存子网组" \
    --subnet-ids subnet-12345678 subnet-87654321 \
    --profile oversea1 \
    --region us-west-2

# 创建Redis缓存集群
aws elasticache create-cache-cluster \
    --cache-cluster-id location-service-cache \
    --cache-node-type cache.t3.micro \
    --engine redis \
    --num-cache-nodes 1 \
    --cache-subnet-group-name location-service-cache-subnet \
    --security-group-ids sg-12345678 \
    --profile oversea1 \
    --region us-west-2
```

### 2. 多区域部署

```bash
# 在备用区域创建Place Index
aws location create-place-index \
    --index-name "CityGeocodingIndex-DR" \
    --data-source "Esri" \
    --description "灾难恢复Place Index" \
    --pricing-plan "RequestBasedUsage" \
    --profile oversea1 \
    --region us-east-1

# 部署Lambda函数到备用区域
aws lambda create-function \
    --function-name city-geocoding-location-service-dr \
    --runtime python3.9 \
    --role arn:aws:iam::ACCOUNT_ID:role/location-service-lambda-role \
    --handler location_service_poc.lambda_handler \
    --zip-file fileb://location-service-deployment.zip \
    --timeout 30 \
    --memory-size 256 \
    --environment Variables='{PLACE_INDEX_NAME=CityGeocodingIndex-DR}' \
    --profile oversea1 \
    --region us-east-1
```

## 安全加固

### 1. VPC配置

```bash
# 创建VPC端点用于Location Service
aws ec2 create-vpc-endpoint \
    --vpc-id vpc-12345678 \
    --service-name com.amazonaws.us-west-2.geo \
    --vpc-endpoint-type Interface \
    --subnet-ids subnet-12345678 \
    --security-group-ids sg-12345678 \
    --profile oversea1 \
    --region us-west-2
```

### 2. API密钥管理

```bash
# 在Parameter Store中存储API密钥
aws ssm put-parameter \
    --name "/location-service/api-keys" \
    --value '["key1", "key2", "key3"]' \
    --type "SecureString" \
    --description "Location Service API密钥" \
    --profile oversea1 \
    --region us-west-2
```

## 运维自动化

### 1. 健康检查脚本

创建 `health_check.py`:

```python
#!/usr/bin/env python3
import boto3
import json
import sys

def health_check():
    """检查Location Service健康状态"""
    try:
        # 检查Place Index状态
        location_client = boto3.client('location', region_name='us-west-2')
        response = location_client.describe_place_index(
            IndexName='CityGeocodingIndex'
        )
        
        if response['Status'] != 'Active':
            print("❌ Place Index状态异常")
            return False
        
        # 测试地理编码功能
        test_response = location_client.search_place_index_for_text(
            IndexName='CityGeocodingIndex',
            Text='北京, 中国',
            MaxResults=1
        )
        
        if not test_response['Results']:
            print("❌ 地理编码功能异常")
            return False
        
        print("✅ Location Service健康检查通过")
        return True
        
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False

if __name__ == "__main__":
    success = health_check()
    sys.exit(0 if success else 1)
```

### 2. 自动化部署脚本

创建 `deploy.sh`:

```bash
#!/bin/bash
set -e

echo "=== Amazon Location Service自动化部署 ==="

# 配置变量
PROFILE="oversea1"
REGION="us-west-2"
STACK_NAME="location-service-geocoding"

# 检查AWS CLI配置
echo "1. 检查AWS CLI配置..."
aws sts get-caller-identity --profile $PROFILE --region $REGION

# 构建部署包
echo "2. 构建Lambda部署包..."
./build_deployment_package.sh

# 部署CloudFormation栈
echo "3. 部署CloudFormation栈..."
aws cloudformation deploy \
    --template-file location-service-stack.yaml \
    --stack-name $STACK_NAME \
    --capabilities CAPABILITY_IAM \
    --profile $PROFILE \
    --region $REGION

# 获取API端点
echo "4. 获取API端点..."
API_ENDPOINT=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --profile $PROFILE \
    --region $REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' \
    --output text)

echo "API端点: $API_ENDPOINT"

# 运行健康检查
echo "5. 运行健康检查..."
python3 health_check.py

echo "✅ 部署完成！"
```

## 故障排除

### 1. 常见问题

#### Place Index创建失败
```bash
# 检查权限
aws iam simulate-principal-policy \
    --policy-source-arn arn:aws:iam::ACCOUNT_ID:role/location-service-role \
    --action-names geo:CreatePlaceIndex \
    --resource-arns "*" \
    --profile oversea1
```

#### Lambda函数超时
```bash
# 增加超时时间
aws lambda update-function-configuration \
    --function-name city-geocoding-location-service \
    --timeout 60 \
    --profile oversea1 \
    --region us-west-2
```

#### API Gateway 5XX错误
```bash
# 检查Lambda日志
aws logs filter-log-events \
    --log-group-name /aws/lambda/city-geocoding-location-service \
    --start-time $(date -d '1 hour ago' +%s)000 \
    --profile oversea1 \
    --region us-west-2
```

### 2. 监控和调试

```bash
# 启用X-Ray追踪
aws lambda update-function-configuration \
    --function-name city-geocoding-location-service \
    --tracing-config Mode=Active \
    --profile oversea1 \
    --region us-west-2

# 查看CloudWatch指标
aws cloudwatch get-metric-statistics \
    --namespace AWS/Lambda \
    --metric-name Duration \
    --dimensions Name=FunctionName,Value=city-geocoding-location-service \
    --start-time $(date -d '1 hour ago' --iso-8601) \
    --end-time $(date --iso-8601) \
    --period 300 \
    --statistics Average \
    --profile oversea1 \
    --region us-west-2
```

## 清理资源

### 1. 删除CloudFormation栈

```bash
# 删除CloudFormation栈
aws cloudformation delete-stack \
    --stack-name location-service-geocoding \
    --profile oversea1 \
    --region us-west-2

# 等待删除完成
aws cloudformation wait stack-delete-complete \
    --stack-name location-service-geocoding \
    --profile oversea1 \
    --region us-west-2
```

### 2. 手动清理资源

```bash
# 删除Place Index
aws location delete-place-index \
    --index-name CityGeocodingIndex \
    --profile oversea1 \
    --region us-west-2

# 删除Lambda函数
aws lambda delete-function \
    --function-name city-geocoding-location-service \
    --profile oversea1 \
    --region us-west-2

# 删除API Gateway
aws apigateway delete-rest-api \
    --rest-api-id $API_ID \
    --profile oversea1 \
    --region us-west-2
```

## 总结

本部署指南提供了Amazon Location Service城市地理编码解决方案的完整部署流程：

### 部署层次
1. **基础部署** - Place Index + 基础测试
2. **Lambda部署** - 无服务器函数
3. **API Gateway部署** - REST API端点
4. **企业级部署** - CloudFormation + 监控
5. **性能优化** - 缓存 + 多区域
6. **安全加固** - VPC + 密钥管理

### 关键特性
- 自动化部署脚本
- 健康检查和监控
- 故障排除指南
- 资源清理流程

### 最佳实践
- 使用CloudFormation管理资源
- 实施监控和告警
- 定期健康检查
- 及时清理测试资源

按照本指南执行，可以确保Amazon Location Service的稳定部署和高效运维。
