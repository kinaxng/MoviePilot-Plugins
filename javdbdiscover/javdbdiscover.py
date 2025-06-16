from typing import List, Optional
import requests
from bs4 import BeautifulSoup

class JavdbDiscover:
    def __init__(self, base_url: str, headers: dict):
        self.base_url = base_url
        self.headers = headers

    def get_page(self, page: int = 1, **kwargs) -> List[dict]:
        """
        获取页面数据
        :param page: 页码
        :param kwargs: 其他参数
        :return: 页面数据列表
        """
        try:
            # 获取页面数据
            page_data = self._get_page_data(page)
            if not page_data:
                return []
            
            # 解析页面数据
            return self._parse_page_data(page_data)
        except Exception as e:
            logger.error(f"获取页面数据失败: {str(e)}")
            return []

    def _get_page_data(self, page: int) -> Optional[str]:
        """
        获取页面数据
        :param page: 页码
        :return: 页面数据
        """
        try:
            # 构建请求URL
            url = f"{self.base_url}/page/{page}"
            
            # 发送请求
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.text
        except Exception as e:
            logger.error(f"获取页面数据失败: {str(e)}")
            return None

    def _parse_page_data(self, html: str) -> List[dict]:
        """
        解析页面数据
        :param html: 页面HTML
        :return: 解析后的数据列表
        """
        try:
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(html, 'html.parser')
            
            # 获取视频列表
            video_items = soup.select('.grid-item')
            
            result = []
            for item in video_items:
                try:
                    # 获取视频标题
                    title = item.select_one('.video-title').text.strip()
                    
                    # 获取视频链接
                    link = item.select_one('a')['href']
                    if not link.startswith('http'):
                        link = f"{self.base_url}{link}"
                    
                    # 获取视频封面
                    cover = item.select_one('img')['src']
                    if not cover.startswith('http'):
                        cover = f"{self.base_url}{cover}"
                    
                    # 获取视频信息
                    info = item.select_one('.meta').text.strip()
                    
                    result.append({
                        'title': title,
                        'link': link,
                        'cover': cover,
                        'info': info
                    })
                except Exception as e:
                    logger.error(f"解析视频项失败: {str(e)}")
                    continue
            
            return result
        except Exception as e:
            logger.error(f"解析页面数据失败: {str(e)}")
            return [] 