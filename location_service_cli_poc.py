#!/usr/bin/env python3
"""
Amazon Location Service POC - 使用AWS CLI版本
Profile: oversea1, Region: us-west-2
"""

import subprocess
import json
import time
import sys
from typing import Dict, List, Optional

class LocationServiceCLIPOC:
    def __init__(self, profile_name="oversea1", region_name="us-west-2"):
        """
        初始化Amazon Location Service CLI客户端
        """
        self.profile_name = profile_name
        self.region_name = region_name
        self.place_index_name = "CityGeocodingIndex"
        
        print(f"✓ 初始化Amazon Location Service CLI客户端")
        print(f"  Profile: {profile_name}")
        print(f"  Region: {region_name}")
        print(f"  Place Index: {self.place_index_name}")
        
        # 检查AWS CLI可用性
        if not self._check_aws_cli():
            raise Exception("AWS CLI不可用")
        
        # 检查Location Service可用性
        if not self._check_location_service():
            raise Exception("Amazon Location Service不可用")
    
    def _check_aws_cli(self) -> bool:
        """检查AWS CLI是否可用"""
        try:
            result = subprocess.run(['aws', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"✓ AWS CLI可用: {result.stdout.strip()}")
                return True
            else:
                print(f"✗ AWS CLI不可用: {result.stderr}")
                return False
        except Exception as e:
            print(f"✗ AWS CLI检查失败: {e}")
            return False
    
    def _check_location_service(self) -> bool:
        """检查Location Service是否可用"""
        try:
            cmd = [
                'aws', 'location', 'list-place-indexes',
                '--profile', self.profile_name,
                '--region', self.region_name
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"✓ Amazon Location Service可用")
                return True
            else:
                print(f"✗ Amazon Location Service不可用: {result.stderr}")
                return False
        except Exception as e:
            print(f"✗ Location Service检查失败: {e}")
            return False
    
    def _run_aws_command(self, service: str, operation: str, parameters: Dict = None) -> Dict:
        """执行AWS CLI命令"""
        cmd = ['aws', service, operation, '--profile', self.profile_name, '--region', self.region_name]
        
        if parameters:
            for key, value in parameters.items():
                cmd.extend([f'--{key}', str(value)])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'data': json.loads(result.stdout) if result.stdout.strip() else {},
                    'command': ' '.join(cmd)
                }
            else:
                return {
                    'success': False,
                    'error': result.stderr.strip(),
                    'command': ' '.join(cmd)
                }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'Command timeout',
                'command': ' '.join(cmd)
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'command': ' '.join(cmd)
            }
    
    def setup_place_index(self, data_source="Esri") -> bool:
        """创建Place Index"""
        print(f"\n=== 设置Place Index ===")
        print(f"索引名称: {self.place_index_name}")
        print(f"数据源: {data_source}")
        
        # 检查是否已存在
        check_result = self._run_aws_command('location', 'describe-place-index', {
            'index-name': self.place_index_name
        })
        
        if check_result['success']:
            print(f"✓ Place Index已存在")
            index_info = check_result['data']
            print(f"  状态: {index_info.get('Status')}")
            print(f"  数据源: {index_info.get('DataSource')}")
            return True
        
        # 创建新的Place Index
        print("Place Index不存在，正在创建...")
        
        create_params = {
            'index-name': self.place_index_name,
            'data-source': data_source,
            'description': f'城市地理编码POC - {data_source}数据源',
            'pricing-plan': 'RequestBasedUsage'
        }
        
        create_result = self._run_aws_command('location', 'create-place-index', create_params)
        
        if create_result['success']:
            print(f"✓ Place Index创建请求已提交")
            index_arn = create_result['data'].get('IndexArn')
            print(f"  ARN: {index_arn}")
            
            # 等待创建完成
            print("等待索引创建完成...")
            max_attempts = 24
            for attempt in range(max_attempts):
                time.sleep(5)
                
                status_result = self._run_aws_command('location', 'describe-place-index', {
                    'index-name': self.place_index_name
                })
                
                if status_result['success']:
                    status = status_result['data'].get('Status')
                    print(f"  状态检查 {attempt + 1}/{max_attempts}: {status}")
                    
                    if status == 'Active':
                        print("✓ Place Index创建完成并已激活")
                        return True
                    elif status == 'Failed':
                        print("✗ Place Index创建失败")
                        return False
                else:
                    print(f"  状态检查失败: {status_result['error']}")
            
            print("✗ 等待超时，Place Index可能仍在创建中")
            return False
        else:
            print(f"✗ 创建Place Index失败: {create_result['error']}")
            return False
    
    def geocode_city(self, city_name: str, country: str = None) -> Dict:
        """地理编码查询"""
        print(f"\n--- 查询城市: {city_name} ---")
        
        # 构建查询文本
        query_text = city_name
        if country:
            query_text = f"{city_name}, {country}"
        
        start_time = time.time()
        
        # 构建搜索参数
        search_params = {
            'index-name': self.place_index_name,
            'text': query_text,
            'max-results': '1',
            'language': 'zh-CN'
        }
        
        result = self._run_aws_command('location', 'search-place-index-for-text', search_params)
        response_time = time.time() - start_time
        
        if result['success']:
            data = result['data']
            results = data.get('Results', [])
            
            if results:
                place_result = results[0]
                place = place_result['Place']
                geometry = place['Geometry']['Point']
                
                geocode_result = {
                    'success': True,
                    'input_city': city_name,
                    'input_country': country,
                    'query_text': query_text,
                    'coordinates': {
                        'latitude': geometry[1],  # Location Service返回[lon, lat]
                        'longitude': geometry[0]
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
                        'relevance': place_result.get('Relevance'),
                        'place_id': place_result.get('PlaceId'),
                        'data_source': data.get('Summary', {}).get('DataSource'),
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
                print(f"  相关性: {place_result.get('Relevance'):.2f}")
                print(f"  响应时间: {response_time:.2f}秒")
                
                return geocode_result
            else:
                print(f"✗ 未找到匹配结果")
                return {
                    'success': False,
                    'input_city': city_name,
                    'input_country': country,
                    'error': '未找到匹配的城市',
                    'response_time_seconds': response_time
                }
        else:
            print(f"✗ 查询失败: {result['error']}")
            return {
                'success': False,
                'input_city': city_name,
                'input_country': country,
                'error': result['error'],
                'response_time_seconds': response_time
            }
    
    def batch_geocode(self, cities: List[tuple], delay: float = 1.0) -> List[Dict]:
        """批量地理编码"""
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
    
    def reverse_geocode(self, latitude: float, longitude: float) -> Dict:
        """反向地理编码"""
        print(f"\n--- 反向地理编码: ({latitude}, {longitude}) ---")
        
        start_time = time.time()
        
        # 构建搜索参数
        search_params = {
            'index-name': self.place_index_name,
            'position': f'{longitude},{latitude}',  # AWS CLI格式: lon,lat
            'max-results': '1',
            'language': 'zh-CN'
        }
        
        result = self._run_aws_command('location', 'search-place-index-for-position', search_params)
        response_time = time.time() - start_time
        
        if result['success']:
            data = result['data']
            results = data.get('Results', [])
            
            if results:
                place_result = results[0]
                place = place_result['Place']
                
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
                        'relevance': place_result.get('Relevance'),
                        'distance': place_result.get('Distance'),
                        'place_id': place_result.get('PlaceId'),
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
                print(f"  相关性: {place_result.get('Relevance'):.2f}")
                print(f"  响应时间: {response_time:.2f}秒")
                
                return reverse_result
            else:
                print(f"✗ 未找到地址信息")
                return {
                    'success': False,
                    'input_coordinates': {'latitude': latitude, 'longitude': longitude},
                    'error': '未找到地址信息',
                    'response_time_seconds': response_time
                }
        else:
            print(f"✗ 反向地理编码失败: {result['error']}")
            return {
                'success': False,
                'input_coordinates': {'latitude': latitude, 'longitude': longitude},
                'error': result['error'],
                'response_time_seconds': response_time
            }
    
    def get_place_index_info(self) -> Dict:
        """获取Place Index信息"""
        result = self._run_aws_command('location', 'describe-place-index', {
            'index-name': self.place_index_name
        })
        
        if result['success']:
            data = result['data']
            return {
                'success': True,
                'index_info': {
                    'name': data.get('IndexName'),
                    'arn': data.get('IndexArn'),
                    'status': data.get('Status'),
                    'data_source': data.get('DataSource'),
                    'description': data.get('Description'),
                    'create_time': data.get('CreateTime'),
                    'update_time': data.get('UpdateTime'),
                    'pricing_plan': data.get('PricingPlan'),
                    'tags': data.get('Tags', {})
                }
            }
        else:
            return {
                'success': False,
                'error': result['error']
            }
    
    def cleanup_resources(self) -> bool:
        """清理测试资源"""
        print(f"\n=== 清理资源 ===")
        
        result = self._run_aws_command('location', 'delete-place-index', {
            'index-name': self.place_index_name
        })
        
        if result['success']:
            print(f"✓ 成功删除Place Index: {self.place_index_name}")
            return True
        else:
            if 'ResourceNotFoundException' in result['error']:
                print(f"Place Index不存在，无需删除")
                return True
            else:
                print(f"✗ 删除Place Index失败: {result['error']}")
                return False

def run_location_service_cli_poc():
    """运行Amazon Location Service CLI POC测试"""
    
    print("=" * 80)
    print("Amazon Location Service 城市地理编码 POC (AWS CLI版本)")
    print("=" * 80)
    print(f"AWS Profile: oversea1")
    print(f"AWS Region: us-west-2")
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    
    try:
        # 初始化服务
        location_service = LocationServiceCLIPOC(
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
            ("New York", "United States")
        ]
        
        single_results = []
        for city, country in test_cities:
            result = location_service.geocode_city(city, country)
            single_results.append(result)
            time.sleep(1)  # 避免请求过于频繁
        
        # 测试2: 批量查询
        print(f"\n{'='*60}")
        print("测试2: 批量地理编码")
        print(f"{'='*60}")
        
        batch_cities = [
            ("深圳", "中国"),
            ("广州", "中国")
        ]
        
        batch_results = location_service.batch_geocode(batch_cities, delay=1.0)
        
        # 测试3: 反向地理编码
        print(f"\n{'='*60}")
        print("测试3: 反向地理编码")
        print(f"{'='*60}")
        
        reverse_test_coords = [
            (40.190632, 116.412144),  # 北京
            (31.231271, 121.470015)   # 上海
        ]
        
        reverse_results = []
        for lat, lon in reverse_test_coords:
            result = location_service.reverse_geocode(lat, lon)
            reverse_results.append(result)
            time.sleep(1)
        
        # 保存测试结果
        all_results = {
            'test_info': {
                'aws_profile': 'oversea1',
                'aws_region': 'us-west-2',
                'place_index_name': location_service.place_index_name,
                'test_timestamp': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
                'data_source': 'Esri',
                'test_method': 'AWS CLI'
            },
            'place_index_info': index_info,
            'single_city_results': single_results,
            'batch_results': batch_results,
            'reverse_geocoding_results': reverse_results
        }
        
        # 保存到文件
        output_file = "location_service_cli_test_results.json"
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
        print("注意: Place Index会产生费用，建议测试完成后删除")
        cleanup_choice = input("是否删除测试创建的Place Index? (y/N): ").strip().lower()
        if cleanup_choice == 'y':
            location_service.cleanup_resources()
        else:
            print("保留Place Index，请注意可能产生的费用")
            print("可以稍后运行以下命令删除:")
            print(f"aws location delete-place-index --index-name {location_service.place_index_name} --profile oversea1 --region us-west-2")
        
    except KeyboardInterrupt:
        print("\n\n用户中断测试")
    except Exception as e:
        print(f"✗ POC测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_location_service_cli_poc()
