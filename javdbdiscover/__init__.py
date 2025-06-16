from typing import Any, List, Dict, Tuple, Optional

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType
from app.utils.http import RequestUtils
from .javdbdiscover import JavdbDiscover


class JavdbDiscover(_PluginBase):
    # 插件名称
    plugin_name = "JavDB探索"
    # 插件描述
    plugin_desc = "让探索支持JavDB的数据浏览。"
    # 插件图标
    plugin_icon = "javdb.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "jxxghp"
    # 作者主页
    author_url = "https://github.com/jxxghp"
    # 插件配置项ID前缀
    plugin_config_prefix = "javdbdiscover_"
    # 加载顺序
    plugin_order = 99
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _proxy = False
    _cookie = None
    _javdb = None

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._cookie = config.get("cookie")
            
            # 初始化JavDB客户端
            if self._enabled:
                headers = {
                    "User-Agent": "Mozilla/5.0",
                    "Cookie": self._cookie or ""
                }
                self._javdb = JavdbDiscover(
                    base_url="https://javdb.com",
                    headers=headers
                )

    def get_state(self) -> bool:
        return self._enabled

    def get_api(self) -> List[Dict[str, Any]]:
        """
        获取插件API
        """
        return [{
            "path": "/javdb_discover",
            "endpoint": self.javdb_discover,
            "methods": ["GET"],
            "summary": "JavDB探索数据源",
            "description": "获取JavDB探索数据",
        }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'proxy',
                                            'label': '使用代理服务器',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'cookie',
                                            'label': 'Cookie',
                                            'placeholder': '请输入JavDB的Cookie'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "proxy": False,
            "cookie": ""
        }

    def javdb_discover(self, apikey: str, query: str = "", page: int = 1, count: int = 30) -> List[schemas.MediaInfo]:
        """
        获取JavDB探索数据
        """
        if apikey != settings.API_TOKEN:
            return []
        
        if not self._enabled or not self._javdb:
            return []
            
        try:
            # 获取页面数据
            results = self._javdb.get_page(page=page)
            if not results:
                return []
                
            # 转换为MediaInfo格式
            media_list = []
            for item in results[:count]:
                media_list.append(schemas.MediaInfo(
                    type="番号",
                    title=item.get('title', ''),
                    year=None,
                    title_year=item.get('title', ''),
                    mediaid_prefix="javdb",
                    media_id=item.get('id', ''),
                    poster_path=item.get('cover', ''),
                    vote_average=None,
                    runtime=None,
                    overview=item.get('info', '')
                ))
            return media_list
        except Exception as e:
            logger.error(f"获取JavDB探索数据失败: {str(e)}")
            return []

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event):
        """
        注册探索数据源
        """
        if not self._enabled or not self._cookie:
            return
            
        event_data: DiscoverSourceEventData = event.event_data
        javdb_source = schemas.DiscoverMediaSource(
            name="JavDB",
            mediaid_prefix="javdb",
            api_path=f"plugin/JavdbDiscover/javdb_discover?apikey={settings.API_TOKEN}",
            filter_params={
                "query": "",
            },
            filter_ui=[
                {
                    "component": "VTextField",
                    "props": {"model": "query", "label": "搜索关键词"}
                }
            ]
        )
        
        if not event_data.extra_sources:
            event_data.extra_sources = [javdb_source]
        else:
            event_data.extra_sources.append(javdb_source)

    def stop_service(self):
        """
        停止服务
        """
        self._javdb = None 