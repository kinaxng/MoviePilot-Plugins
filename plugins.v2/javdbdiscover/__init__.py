from typing import Any, List, Dict, Tuple, Optional

from cachetools import cached, TTLCache

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType
from app.utils.http import RequestUtils

class javdbdiscover(_PluginBase):
    plugin_name = "JavDB探索"
    plugin_desc = "让探索支持JavDB的数据浏览。"
    plugin_icon = "Bilibili_E.png"  # 可替换为合适的JavDB图标
    plugin_version = "0.1"
    plugin_author = "copilot"
    author_url = "https://github.com/chris-2s/tissue"
    plugin_config_prefix = "javdbdiscover_"
    plugin_order = 100
    auth_level = 1

    _enabled = False
    _proxy = False
    _cookie = None

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._cookie = config.get("cookie")

    def get_state(self) -> bool:
        return self._enabled

    def get_api(self) -> List[Dict[str, Any]]:
        return [{
            "path": "/javdb_discover",
            "endpoint": self.javdb_discover,
            "methods": ["GET"],
            "summary": "JavDB探索数据源",
            "description": "获取JavDB探索数据",
        }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 4},
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {'model': 'enabled', 'label': '启用插件'}
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {'cols': 12, 'md': 4},
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {'model': 'proxy', 'label': '使用代理服务器'}
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
                                'props': {'cols': 12},
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {'model': 'cookie', 'label': 'JavDB Cookie'}
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

    @cached(cache=TTLCache(maxsize=32, ttl=1800))
    def __request(self, query: str, page: int = 1):
        """
        请求JavDB数据，参考tissue实现
        """
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Cookie": self._cookie or ""
        }
        url = f"https://javdb.com/search?q={query}&page={page}"
        res = RequestUtils(headers=headers).get_res(
            url,
            proxies=settings.PROXY if self._proxy else None
        )
        if res is None or not res.ok:
            logger.error(f"请求JavDB失败: {res.text if res else '无响应'}")
            return []
        return res.text

    def javdb_discover(self, apikey: str, query: str = "", page: int = 1, count: int = 30) -> List[schemas.MediaInfo]:
        """
        获取JavDB探索数据
        """
        if apikey != settings.API_TOKEN:
            return []
        try:
            html = self.__request(query, page)
            # 解析HTML，提取影片信息，参考tissue的parse逻辑
            # 这里只做简单示例，实际可用BeautifulSoup等
            import re
            pattern = re.compile(r'<a class="box" href="/v/(.*?)">.*?<img src="(.*?)".*?alt="(.*?)"', re.S)
            results = []
            for gid, img, title in pattern.findall(html):
                results.append(schemas.MediaInfo(
                    type="番号",
                    title=title.strip(),
                    year=None,
                    title_year=title.strip(),
                    mediaid_prefix="javdb",
                    media_id=gid,
                    poster_path=img,
                    vote_average=None,
                    runtime=None,
                    overview=None
                ))
            return results[:count]
        except Exception as err:
            logger.error(str(err))
            return []

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event):
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
        pass
