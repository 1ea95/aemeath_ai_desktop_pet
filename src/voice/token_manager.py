"""阿里云ASR鉴权Token管理器

自动获取和管理阿里云ASR服务的鉴权token
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

try:
    from aliyunsdkcore.client import AcsClient
    from aliyunsdkcore.request import CommonRequest
    ALIYUN_SDK_AVAILABLE = True
except ImportError:
    ALIYUN_SDK_AVAILABLE = False
    print("警告: 阿里云SDK未安装，请运行: pip install aliyun-python-sdk-core==2.15.1")

from src.config import load_config, save_config, update_config


class TokenManager:
    """阿里云ASR鉴权Token管理器
    
    自动获取和管理阿里云ASR服务的鉴权token，支持自动刷新
    """
    
    def __init__(self):
        """初始化Token管理器"""
        print(f"TokenManager.__init__ 被调用，线程ID: {threading.get_ident()}")
        self.token = None
        self.expire_time = None
        self.auto_refresh_enabled = True
        self.refresh_thread = None
        self.refresh_lock = threading.Lock()
        
        # 从配置中加载阿里云访问凭证
        print("加载阿里云访问凭证...")
        self._load_credentials()
        
        # 尝试从配置中加载已有的token
        print("加载已有token...")
        self._load_existing_token()
        
        # 启动自动刷新线程
        if self.auto_refresh_enabled and self._has_valid_credentials():
            print("启动自动刷新线程...")
            self._start_auto_refresh()
        else:
            print(f"不启动自动刷新线程，auto_refresh_enabled={self.auto_refresh_enabled}, has_credentials={self._has_valid_credentials()}")
    
    def _load_credentials(self):
        """从环境变量或配置中加载阿里云访问凭证"""
        # 优先从环境变量获取
        self.access_key_id = os.getenv('ALIYUN_AK_ID')
        self.access_key_secret = os.getenv('ALIYUN_AK_SECRET')
        self.region = os.getenv('ALIYUN_REGION', 'cn-shanghai')
        
        # 如果环境变量不存在，从配置文件获取
        config = load_config()
        if not self.access_key_id:
            self.access_key_id = config.get('aliyun_access_key_id', '')
        if not self.access_key_secret:
            self.access_key_secret = config.get('aliyun_access_key_secret', '')
        
        # 保存凭证到配置文件（如果从环境变量获取）
        if os.getenv('ALIYUN_AK_ID') and os.getenv('ALIYUN_AK_SECRET'):
            update_config(
                aliyun_access_key_id=self.access_key_id,
                aliyun_access_key_secret=self.access_key_secret
            )
    
    def _load_existing_token(self):
        """从配置中加载已有的token"""
        config = load_config()
        saved_token = config.get('asr_token', '')
        saved_expire_time = config.get('asr_token_expire_time', 0)
        
        if saved_token and saved_expire_time:
            # 检查token是否仍然有效
            try:
                # 判断时间戳格式并转换
                # 当前时间是2026年，时间戳约为1770000000（秒级）或1770000000000（毫秒级）
                if saved_expire_time > 10**12:  # 毫秒时间戳
                    expire_datetime = datetime.fromtimestamp(saved_expire_time / 1000)
                elif saved_expire_time > 10**9:  # 秒时间戳（2026年约为1770000000）
                    expire_datetime = datetime.fromtimestamp(saved_expire_time)
                else:  # 可能是毫秒时间戳但数值较小
                    expire_datetime = datetime.fromtimestamp(saved_expire_time / 1000)
                    
                if datetime.now() < expire_datetime - timedelta(minutes=5):  # 提前5分钟刷新
                    self.token = saved_token
                    self.expire_time = expire_datetime
                    print(f"从配置中加载有效token，过期时间: {self.expire_time}")
                else:
                    print(f"配置中的token已过期，过期时间: {expire_datetime}")
            except Exception as e:
                print(f"解析token过期时间失败: {e}，时间戳: {saved_expire_time}")
    
    def _has_valid_credentials(self) -> bool:
        """检查是否有有效的阿里云访问凭证"""
        return bool(self.access_key_id and self.access_key_secret)
    
    def _is_token_valid(self) -> bool:
        """检查当前token是否仍然有效"""
        if not self.token or not self.expire_time:
            return False
        
        # 提前5分钟刷新token
        return datetime.now() < self.expire_time - timedelta(minutes=5)
    
    def _fetch_new_token(self) -> Optional[str]:
        """获取新的鉴权token"""
        print(f"_fetch_new_token 被调用，线程ID: {threading.get_ident()}")
        if not ALIYUN_SDK_AVAILABLE:
            print("阿里云SDK未安装，无法获取token")
            return None
            
        if not self._has_valid_credentials():
            print("缺少有效的阿里云访问凭证")
            return None
        
        try:
            # 创建AcsClient实例
            client = AcsClient(
                self.access_key_id,
                self.access_key_secret,
                self.region
            )
            
            # 创建request，并设置参数
            request = CommonRequest()
            request.set_method('POST')
            request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')
            request.set_version('2019-02-28')
            request.set_action_name('CreateToken')
            
            # 发送请求
            response = client.do_action_with_exception(request)
            response_json = json.loads(response)
            
            # 调试：打印原始响应
            print(f"阿里云API响应: {response_json}")
            
            if 'Token' in response_json and 'Id' in response_json['Token']:
                new_token = response_json['Token']['Id']
                expire_timestamp = response_json['Token']['ExpireTime']
                
                # 更新token和过期时间
                self.token = new_token
                
                # 判断时间戳格式并转换
                # 当前时间是2026年，时间戳约为1770000000（秒级）或1770000000000（毫秒级）
                # 如果时间戳大于10^12，可能是毫秒；如果大于10^9，可能是秒；否则可能是毫秒
                if expire_timestamp > 10**12:  # 毫秒时间戳
                    self.expire_time = datetime.fromtimestamp(expire_timestamp / 1000)
                elif expire_timestamp > 10**9:  # 秒时间戳（2026年约为1770000000）
                    self.expire_time = datetime.fromtimestamp(expire_timestamp)
                else:  # 可能是毫秒时间戳但数值较小
                    self.expire_time = datetime.fromtimestamp(expire_timestamp / 1000)
                
                # 保存到配置
                self._save_token_to_config()
                
                print(f"获取新token成功，过期时间: {self.expire_time}")
                print(f"原始时间戳: {expire_timestamp}")
                return new_token
            else:
                print(f"获取token失败: 响应格式不正确 - {response}")
                return None
                
        except Exception as e:
            print(f"获取token时发生异常: {e}")
            return None
    
    def _save_token_to_config(self):
        """保存token到配置文件"""
        if self.token and self.expire_time:
            expire_timestamp = int(self.expire_time.timestamp())
            update_config(
                asr_token=self.token,
                asr_token_expire_time=expire_timestamp
            )
    
    def _refresh_worker(self):
        """自动刷新token的工作线程"""
        print("Token自动刷新线程已启动")
        while self.auto_refresh_enabled:
            try:
                # 检查token是否需要刷新
                if not self._is_token_valid():
                    print("Token已过期或即将过期，正在刷新...")
                    with self.refresh_lock:
                        self._fetch_new_token()
                
                # 每分钟检查一次
                time.sleep(60)
                
            except Exception as e:
                print(f"Token刷新线程异常: {e}")
                time.sleep(60)  # 出错后等待一分钟再试
        
        print("Token自动刷新线程已停止")
    
    def _start_auto_refresh(self):
        """启动自动刷新线程"""
        if self.refresh_thread and self.refresh_thread.is_alive():
            return
        
        self.refresh_thread = threading.Thread(target=self._refresh_worker, daemon=True)
        self.refresh_thread.start()
    
    def get_token(self, force_refresh: bool = False) -> Optional[str]:
        """获取有效的token
        
        参数:
            force_refresh: 是否强制刷新token
            
        返回:
            有效的token字符串，如果获取失败则返回None
        """
        if not self._has_valid_credentials():
            print("缺少有效的阿里云访问凭证，无法获取token")
            return None
        
        # 如果token无效或强制刷新，则获取新token
        if force_refresh or not self._is_token_valid():
            with self.refresh_lock:
                return self._fetch_new_token()
        
        return self.token
    
    def stop_auto_refresh(self):
        """停止自动刷新"""
        self.auto_refresh_enabled = False
        if self.refresh_thread and self.refresh_thread.is_alive():
            self.refresh_thread.join(timeout=5)
    
    def get_token_info(self) -> Dict[str, Any]:
        """获取token信息
        
        返回:
            包含token信息的字典
        """
        return {
            'has_token': bool(self.token),
            'is_valid': self._is_token_valid(),
            'expire_time': self.expire_time.isoformat() if self.expire_time else None,
            'has_credentials': self._has_valid_credentials(),
            'auto_refresh_enabled': self.auto_refresh_enabled
        }


# 全局token管理器实例
_token_manager: Optional[TokenManager] = None


def get_token_manager() -> TokenManager:
    """获取全局token管理器实例
    
    返回:
        TokenManager实例
    """
    global _token_manager
    if _token_manager is None:
        print("创建新的TokenManager实例")
        _token_manager = TokenManager()
    else:
        print("使用已存在的TokenManager实例")
    return _token_manager


def get_asr_token(force_refresh: bool = False) -> Optional[str]:
    """获取ASR服务的有效token
    
    参数:
        force_refresh: 是否强制刷新token
        
    返回:
        有效的token字符串，如果获取失败则返回None
    """
    return get_token_manager().get_token(force_refresh)


def setup_aliyun_credentials(access_key_id: str, access_key_secret: str, region: str = 'cn-shanghai'):
    """设置阿里云访问凭证
    
    参数:
        access_key_id: 阿里云访问密钥ID
        access_key_secret: 阿里云访问密钥Secret
        region: 区域，默认为cn-shanghai
    """
    # 保存到配置
    update_config(
        aliyun_access_key_id=access_key_id,
        aliyun_access_key_secret=access_key_secret
    )
    
    # 更新token管理器的凭证
    token_manager = get_token_manager()
    token_manager.access_key_id = access_key_id
    token_manager.access_key_secret = access_key_secret
    token_manager.region = region
    
    # 重启自动刷新线程
    token_manager.stop_auto_refresh()
    token_manager.auto_refresh_enabled = True
    token_manager._start_auto_refresh()
    
    print("阿里云访问凭证已更新")
