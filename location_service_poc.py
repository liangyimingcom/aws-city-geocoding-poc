#!/usr/bin/env python3
"""
Amazon Location Service POC
使用AWS Location Service进行城市地理编码
Profile: oversea1, Region: us-west-2
"""

import boto3
import json
import time
from typing import Dict, List, Optional
from botocore.exceptions import ClientError, NoCredentialsError

class AmazonLocationServicePOC:
    def __init__(self, profile_name="oversea1", region_name="us-west-2"):
        """
        初始化Amazon Location Service客户端
        
        Args:
            profile_name: AWS profile名称
            region_name: AWS区域
        """
        self.profile_name = profile_name
        self.region_name = region_name
        self.place_index_name = "CityGeocodingIndex"
        
        try:
            # 创建会话和客户端
            session = boto3.Session(profile_name=profile_name)
            self.location_client = session.client('location', region_name=region_name)
            
            print(f"✓ 成功初始化Amazon Location Service")
            print(f"  Profile: {profile_name}")
            print(f"  Region: {region_name}")
            print(f"  Place Index: {self.place_index_name}")
            
        except NoCredentialsError:
            print(f"✗ 错误: 无法找到AWS凭证 (Profile: {profile_name})")
            raise
        except Exception as e:
            print(f"✗ 初始化失败: {e}")
            raise
    
    def setup_place_index(self, data_source="Esri"):
        """
        创建Place Index（地理编码索引）
        
        Args:
            data_source: 数据源提供商 (Esri, HERE, Grab)
        """
        print(f"\n=== 设置Place Index ===")
        print(f"索引名称: {self.place_index_name}")
        print(f"数据源: {data_source}")
        
        try:
            # 检查索引是否已存在
            try:
                response = self.location_client.describe_place_index(
                    IndexName=self.place_index_name
                )
                print(f"✓ Place Index已存在")
                print(f"  状态: {response.get('Status')}")
                print(f"  数据源: {response.get('DataSource')}")
                return True
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    print("Place Index不存在，正在创建...")
                else:
                    raise
            
            # 创建新的Place Index
            response = self.location_client.create_place_index(
                IndexName=self.place_index_name,
                DataSource=data_source,
                Description=f"城市地理编码POC - {data_source}数据源",
                Tags={
                    'Project': 'CityGeocodingPOC',
                    'Environment': 'Test',
                    'DataSource': data_source
                }
            )
            
            print(f"✓ 成功创建Place Index")
            print(f"  ARN: {response.get('IndexArn')}")
            
            # 等待索引创建完成
            print("等待索引创建完成...")
            waiter = self.location_client.get_waiter('place_index_active')
            waiter.wait(
                IndexName=self.place_index_name,
                WaiterConfig={
                    'Delay': 5,
                    'MaxAttempts': 24  # 最多等待2分钟
                }
            )
            
            print("✓ Place Index创建完成并已激活")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"✗ 创建Place Index失败: {error_code} - {error_message}")
            return False
        except Exception as e:
            print(f"✗ 未知错误: {e}")
            return False
    
    def geocode_city(self, city_name: str, country: str = None, max_results: int = 1) -> Optional[Dict]:
        """
        使用Amazon Location Service进行地理编码
        
        Args:
            city_name: 城市名称
            country: 国家名称（可选）
            max_results: 最大结果数量
        
        Returns:
            地理编码结果字典
        """
        print(f"\n--- 查询城市: {city_name} ---")
        
        # 构建查询文本
        query_text = city_name
        if country:
            query_text = f"{city_name}, {country}"
        
        try:
            start_time = time.time()
            
            response = self.location_client.search_place_index_for_text(
                IndexName=self.place_index_name,
                Text=query_text,
                MaxResults=max_results,
                Language='zh-CN'  # 优先中文结果
            )
            
            response_time = time.time() - start_time
            
            if response.get('Results'):
                result = response['Results'][0]
                place = result['Place']
                
                geocode_result = {
                    'success': True,
                    'input_city': city_name,
                    'input_country': country,
                    'query_text': query_text,
                    'coordinates': {
                        'latitude': place['Geometry']['Point'][1],
                        'longitude': place['Geometry']['Point'][0]
                    },
                    'address': {
                        'label': place.get('Label'),
                        'country': place.get('Country'),
                        'region': place.get('Region'),
                        'sub_region': place.get('SubRegion'),
                        'municipality': place.get('Municipality'),
                        'postal_code': place.get('PostalCode')
                    },
                    'metadata': {
                        'relevance': result.get('Relevance'),
                        'place_id': result.get('PlaceId'),
                        'data_source': response.get('Summary', {}).get('DataSource'),
                        'response_time_seconds': response_time
                    },
                    'aws_info': {
                        'profile': self.profile_name,
                        'region': self.region_name,
                        'place_index': self.place_index_name,
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
                    }
                }
                
                print(f"✓ 查询成功")
                print(f"  坐标: ({geocode_result['coordinates']['latitude']:.6f}, {geocode_result['coordinates']['longitude']:.6f})")
                print(f"  地址: {place.get('Label')}")
                print(f"  相关性: {result.get('Relevance'):.2f}")
                print(f"  响应时间: {response_time:.2f}秒")
                
                return geocode_result
            else:
                print(f"✗ 未找到匹配结果")
                return {
                    'success': False,
                    'input_city': city_name,
                    'input_country': country,
                    'error': '未找到匹配的城市',
                    'aws_info': {
                        'profile': self.profile_name,
                        'region': self.region_name,
                        'place_index': self.place_index_name
                    }
                }
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"✗ 查询失败: {error_code} - {error_message}")
            
            return {
                'success': False,
                'input_city': city_name,
                'input_country': country,
                'error': f"{error_code}: {error_message}",
                'aws_info': {
                    'profile': self.profile_name,
                    'region': self.region_name,
                    'place_index': self.place_index_name
                }
            }
        except Exception as e:
            print(f"✗ 未知错误: {e}")
            return {
                'success': False,
                'input_city': city_name,
                'input_country': country,
                'error': str(e),
                'aws_info': {
                    'profile': self.profile_name,
                    'region': self.region_name,
                    'place_index': self.place_index_name
                }
            }
    
    def batch_geocode(self, cities: List[tuple], delay: float = 0.5) -> List[Dict]:
        """
        批量地理编码
        
        Args:
            cities: 城市列表，格式为 [(city, country), ...]
            delay: 请求间隔
        
        Returns:
            结果列表
        """
        print(f"\n=== 批量地理编码 ===")
        print(f"城市数量: {len(cities)}")
        print(f"请求间隔: {delay}秒")
        
        results = []
        success_count = 0
        
        for i, (city, country) in enumerate(cities, 1):
            print(f"\n[{i}/{len(cities)}] 处理: {city}")
            
            result = self.geocode_city(city, country)
            results.append(result)
            
            if result['success']:
                success_count += 1
            
            # 避免请求过于频繁
            if i < len(cities):
                time.sleep(delay)
        
        print(f"\n批量处理完成: 成功 {success_count}/{len(cities)} 个城市")
        return results
    
    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Dict]:
        """
        反向地理编码（坐标转地址）
        
        Args:
            latitude: 纬度
            longitude: 经度
        
        Returns:
            反向地理编码结果
        """
        print(f"\n--- 反向地理编码: ({latitude}, {longitude}) ---")
        
        try:
            start_time = time.time()
            
            response = self.location_client.search_place_index_for_position(
                IndexName=self.place_index_name,
                Position=[longitude, latitude],  # 注意：Location Service使用[lon, lat]格式
                MaxResults=1,
                Language='zh-CN'
            )
            
            response_time = time.time() - start_time
            
            if response.get('Results'):
                result = response['Results'][0]
                place = result['Place']
                
                reverse_result = {
                    'success': True,
                    'input_coordinates': {
                        'latitude': latitude,
                        'longitude': longitude
                    },
                    'address': {
                        'label': place.get('Label'),
                        'country': place.get('Country'),
                        'region': place.get('Region'),
                        'sub_region': place.get('SubRegion'),
                        'municipality': place.get('Municipality'),
                        'neighborhood': place.get('Neighborhood'),
                        'postal_code': place.get('PostalCode')
                    },
                    'metadata': {
                        'relevance': result.get('Relevance'),
                        'distance': result.get('Distance'),
                        'place_id': result.get('PlaceId'),
                        'response_time_seconds': response_time
                    },
                    'aws_info': {
                        'profile': self.profile_name,
                        'region': self.region_name,
                        'place_index': self.place_index_name,
                        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
                    }
                }
                
                print(f"✓ 反向地理编码成功")
                print(f"  地址: {place.get('Label')}")
                print(f"  相关性: {result.get('Relevance'):.2f}")
                print(f"  响应时间: {response_time:.2f}秒")
                
                return reverse_result
            else:
                print(f"✗ 未找到地址信息")
                return {
                    'success': False,
                    'input_coordinates': {'latitude': latitude, 'longitude': longitude},
                    'error': '未找到地址信息'
                }
                
        except Exception as e:
            print(f"✗ 反向地理编码失败: {e}")
            return {
                'success': False,
                'input_coordinates': {'latitude': latitude, 'longitude': longitude},
                'error': str(e)
            }
    
    def get_place_index_info(self) -> Dict:
        """获取Place Index信息"""
        try:
            response = self.location_client.describe_place_index(
                IndexName=self.place_index_name
            )
            return {
                'success': True,
                'index_info': {
                    'name': response.get('IndexName'),
                    'arn': response.get('IndexArn'),
                    'status': response.get('Status'),
                    'data_source': response.get('DataSource'),
                    'description': response.get('Description'),
                    'create_time': response.get('CreateTime').isoformat() if response.get('CreateTime') else None,
                    'update_time': response.get('UpdateTime').isoformat() if response.get('UpdateTime') else None,
                    'pricing_plan': response.get('PricingPlan'),
                    'tags': response.get('Tags', {})
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_resources(self):
        """清理测试资源"""
        print(f"\n=== 清理资源 ===")
        
        try:
            self.location_client.delete_place_index(
                IndexName=self.place_index_name
            )
            print(f"✓ 成功删除Place Index: {self.place_index_name}")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"Place Index不存在，无需删除")
                return True
            else:
                print(f"✗ 删除Place Index失败: {e}")
                return False
        except Exception as e:
            print(f"✗ 清理资源时出错: {e}")
            return False

def run_location_service_poc():
    """运行Amazon Location Service POC测试"""
    
    print("=" * 80)
    print("Amazon Location Service 城市地理编码 POC")
    print("=" * 80)
    print(f"AWS Profile: oversea1")
    print(f"AWS Region: us-west-2")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    
    try:
        # 初始化服务
        location_service = AmazonLocationServicePOC(
            profile_name="oversea1",
            region_name="us-west-2"
        )
        
        # 设置Place Index
        if not location_service.setup_place_index(data_source="Esri"):
            print("Place Index设置失败，退出测试")
            return
        
        # 获取索引信息
        index_info = location_service.get_place_index_info()
        if index_info['success']:
            print(f"\n=== Place Index信息 ===")
            info = index_info['index_info']
            print(f"名称: {info['name']}")
            print(f"状态: {info['status']}")
            print(f"数据源: {info['data_source']}")
            print(f"定价计划: {info['pricing_plan']}")
        
        # 测试1: 单个城市查询
        print(f"\n{'='*60}")
        print("测试1: 单个城市地理编码")
        print(f"{'='*60}")
        
        test_cities = [
            ("北京", "中国"),
            ("上海", "中国"),
            ("New York", "United States"),
            ("London", "United Kingdom"),
            ("Tokyo", "Japan")
        ]
        
        single_results = []
        for city, country in test_cities:
            result = location_service.geocode_city(city, country)
            single_results.append(result)
            time.sleep(0.5)  # 避免请求过于频繁
        
        # 测试2: 批量查询
        print(f"\n{'='*60}")
        print("测试2: 批量地理编码")
        print(f"{'='*60}")
        
        batch_cities = [
            ("深圳", "中国"),
            ("广州", "中国"),
            ("杭州", "中国"),
            ("成都", "中国")
        ]
        
        batch_results = location_service.batch_geocode(batch_cities, delay=0.5)
        
        # 测试3: 反向地理编码
        print(f"\n{'='*60}")
        print("测试3: 反向地理编码")
        print(f"{'='*60}")
        
        reverse_test_coords = [
            (40.190632, 116.412144),  # 北京
            (31.231271, 121.470015),  # 上海
            (22.544574, 114.054543)   # 深圳
        ]
        
        reverse_results = []
        for lat, lon in reverse_test_coords:
            result = location_service.reverse_geocode(lat, lon)
            reverse_results.append(result)
            time.sleep(0.5)
        
        # 保存测试结果
        all_results = {
            'test_info': {
                'aws_profile': 'oversea1',
                'aws_region': 'us-west-2',
                'place_index_name': location_service.place_index_name,
                'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
                'data_source': 'Esri'
            },
            'place_index_info': index_info,
            'single_city_results': single_results,
            'batch_results': batch_results,
            'reverse_geocoding_results': reverse_results
        }
        
        # 保存到文件
        output_file = "location_service_test_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n{'='*60}")
        print("测试汇总")
        print(f"{'='*60}")
        
        single_success = len([r for r in single_results if r['success']])
        batch_success = len([r for r in batch_results if r['success']])
        reverse_success = len([r for r in reverse_results if r['success']])
        
        print(f"单个城市查询: {single_success}/{len(single_results)} 成功")
        print(f"批量查询: {batch_success}/{len(batch_results)} 成功")
        print(f"反向地理编码: {reverse_success}/{len(reverse_results)} 成功")
        print(f"测试结果已保存到: {output_file}")
        
        # 询问是否清理资源
        print(f"\n{'='*60}")
        cleanup_choice = input("是否删除测试创建的Place Index? (y/N): ").strip().lower()
        if cleanup_choice == 'y':
            location_service.cleanup_resources()
        else:
            print("保留Place Index，请注意可能产生的费用")
        
    except Exception as e:
        print(f"✗ POC测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_location_service_poc()
