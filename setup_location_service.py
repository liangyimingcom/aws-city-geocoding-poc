#!/usr/bin/env python3
"""
Amazon Location Service 设置脚本
用于创建和配置必要的资源
"""

import boto3
import json
import time
from botocore.exceptions import ClientError

def setup_location_service(profile_name="oversea1", region_name="us-west-2"):
    """设置Amazon Location Service资源"""
    
    print("=" * 60)
    print("Amazon Location Service 资源设置")
    print("=" * 60)
    
    try:
        # 创建会话和客户端
        session = boto3.Session(profile_name=profile_name)
        location_client = session.client('location', region_name=region_name)
        
        print(f"✓ AWS会话创建成功")
        print(f"  Profile: {profile_name}")
        print(f"  Region: {region_name}")
        
        # 检查Location Service可用性
        try:
            location_client.list_place_indexes()
            print(f"✓ Amazon Location Service可用")
        except Exception as e:
            print(f"✗ Amazon Location Service不可用: {e}")
            return False
        
        # 创建Place Index配置
        place_index_configs = [
            {
                'name': 'CityGeocodingIndex-Esri',
                'data_source': 'Esri',
                'description': '使用Esri数据源的城市地理编码索引'
            },
            {
                'name': 'CityGeocodingIndex-HERE',
                'data_source': 'Here',
                'description': '使用HERE数据源的城市地理编码索引'
            }
        ]
        
        created_indexes = []
        
        for config in place_index_configs:
            print(f"\n--- 创建Place Index: {config['name']} ---")
            
            try:
                # 检查是否已存在
                try:
                    response = location_client.describe_place_index(
                        IndexName=config['name']
                    )
                    print(f"✓ Place Index已存在: {config['name']}")
                    created_indexes.append(config['name'])
                    continue
                except ClientError as e:
                    if e.response['Error']['Code'] != 'ResourceNotFoundException':
                        raise
                
                # 创建新的Place Index
                response = location_client.create_place_index(
                    IndexName=config['name'],
                    DataSource=config['data_source'],
                    Description=config['description'],
                    PricingPlan='RequestBasedUsage',  # 按请求付费
                    Tags={
                        'Project': 'CityGeocodingPOC',
                        'Environment': 'Test',
                        'DataSource': config['data_source'],
                        'CreatedBy': 'SetupScript'
                    }
                )
                
                print(f"✓ Place Index创建请求已提交")
                print(f"  ARN: {response.get('IndexArn')}")
                
                # 等待创建完成
                print("  等待创建完成...")
                waiter = location_client.get_waiter('place_index_active')
                waiter.wait(
                    IndexName=config['name'],
                    WaiterConfig={
                        'Delay': 5,
                        'MaxAttempts': 24
                    }
                )
                
                print(f"✓ Place Index创建完成: {config['name']}")
                created_indexes.append(config['name'])
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                error_message = e.response['Error']['Message']
                print(f"✗ 创建失败: {error_code} - {error_message}")
                
                # 常见错误处理
                if error_code == 'ValidationException':
                    print("  可能原因: 数据源不支持或配置错误")
                elif error_code == 'AccessDeniedException':
                    print("  可能原因: 权限不足，请检查IAM权限")
                elif error_code == 'ThrottlingException':
                    print("  可能原因: 请求过于频繁，稍后重试")
                
            except Exception as e:
                print(f"✗ 未知错误: {e}")
        
        # 显示创建结果
        print(f"\n{'='*60}")
        print("资源创建汇总")
        print(f"{'='*60}")
        print(f"成功创建的Place Index: {len(created_indexes)}")
        for index_name in created_indexes:
            print(f"  - {index_name}")
        
        # 获取详细信息
        if created_indexes:
            print(f"\n详细信息:")
            for index_name in created_indexes:
                try:
                    response = location_client.describe_place_index(
                        IndexName=index_name
                    )
                    print(f"\n{index_name}:")
                    print(f"  状态: {response.get('Status')}")
                    print(f"  数据源: {response.get('DataSource')}")
                    print(f"  定价计划: {response.get('PricingPlan')}")
                    print(f"  创建时间: {response.get('CreateTime')}")
                except Exception as e:
                    print(f"  获取信息失败: {e}")
        
        # 保存配置信息
        config_info = {
            'setup_info': {
                'aws_profile': profile_name,
                'aws_region': region_name,
                'setup_timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
            },
            'created_indexes': created_indexes,
            'available_data_sources': ['Esri', 'Here'],
            'pricing_plan': 'RequestBasedUsage'
        }
        
        with open('location_service_config.json', 'w', encoding='utf-8') as f:
            json.dump(config_info, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n配置信息已保存到: location_service_config.json")
        
        return len(created_indexes) > 0
        
    except Exception as e:
        print(f"✗ 设置失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_permissions(profile_name="oversea1", region_name="us-west-2"):
    """检查必要的权限"""
    
    print("\n=== 权限检查 ===")
    
    try:
        session = boto3.Session(profile_name=profile_name)
        location_client = session.client('location', region_name=region_name)
        iam_client = session.client('iam', region_name=region_name)
        
        required_permissions = [
            'location:CreatePlaceIndex',
            'location:DescribePlaceIndex',
            'location:ListPlaceIndexes',
            'location:SearchPlaceIndexForText',
            'location:SearchPlaceIndexForPosition',
            'location:DeletePlaceIndex'
        ]
        
        print("检查Location Service权限...")
        
        # 尝试列出现有索引
        try:
            location_client.list_place_indexes()
            print("✓ 基本读取权限正常")
        except Exception as e:
            print(f"✗ 基本读取权限不足: {e}")
        
        print(f"\n需要的权限:")
        for permission in required_permissions:
            print(f"  - {permission}")
        
        print(f"\n建议的IAM策略:")
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "location:*"
                    ],
                    "Resource": "*"
                }
            ]
        }
        print(json.dumps(policy, indent=2))
        
    except Exception as e:
        print(f"权限检查失败: {e}")

def cleanup_resources(profile_name="oversea1", region_name="us-west-2"):
    """清理测试资源"""
    
    print("\n=== 资源清理 ===")
    
    try:
        session = boto3.Session(profile_name=profile_name)
        location_client = session.client('location', region_name=region_name)
        
        # 获取所有Place Index
        response = location_client.list_place_indexes()
        indexes = response.get('Entries', [])
        
        test_indexes = [
            idx for idx in indexes 
            if idx['IndexName'].startswith('CityGeocodingIndex')
        ]
        
        if not test_indexes:
            print("没有找到测试相关的Place Index")
            return
        
        print(f"找到 {len(test_indexes)} 个测试相关的Place Index:")
        for idx in test_indexes:
            print(f"  - {idx['IndexName']} ({idx['DataSource']})")
        
        confirm = input("\n确认删除这些资源? (y/N): ").strip().lower()
        if confirm != 'y':
            print("取消删除操作")
            return
        
        # 删除资源
        for idx in test_indexes:
            try:
                location_client.delete_place_index(
                    IndexName=idx['IndexName']
                )
                print(f"✓ 已删除: {idx['IndexName']}")
            except Exception as e:
                print(f"✗ 删除失败 {idx['IndexName']}: {e}")
        
        print("资源清理完成")
        
    except Exception as e:
        print(f"清理失败: {e}")

def main():
    """主函数"""
    
    print("Amazon Location Service 管理工具")
    print("=" * 60)
    
    while True:
        print("\n选择操作:")
        print("1. 设置Location Service资源")
        print("2. 检查权限")
        print("3. 清理测试资源")
        print("4. 退出")
        
        choice = input("\n请选择 (1-4): ").strip()
        
        if choice == '1':
            setup_location_service()
        elif choice == '2':
            check_permissions()
        elif choice == '3':
            cleanup_resources()
        elif choice == '4':
            print("退出")
            break
        else:
            print("无效选择，请重试")

if __name__ == "__main__":
    main()
