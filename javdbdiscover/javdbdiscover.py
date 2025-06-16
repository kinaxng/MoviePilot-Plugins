from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from app.log import logger

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
                logger.error("获取页面数据为空")
                return []
            
            # 解析页面数据
            result = self._parse_page_data(page_data)
            if not result:
                logger.warning(f"页面 {page} 未解析到数据")
            return result
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
            logger.debug(f"请求URL: {url}")
            
            # 发送请求
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            return response.text
        except requests.RequestException as e:
            logger.error(f"请求页面失败: {str(e)}")
            return None
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
            if not video_items:
                logger.warning("未找到视频列表元素")
                return []
            
            result = []
            for item in video_items:
                try:
                    # 获取视频标题
                    title_elem = item.select_one('.video-title')
                    if not title_elem:
                        logger.warning("未找到视频标题元素")
                        continue
                    title = title_elem.text.strip()
                    
                    # 获取视频链接
                    link_elem = item.select_one('a')
                    if not link_elem or 'href' not in link_elem.attrs:
                        logger.warning("未找到视频链接元素")
                        continue
                    link = link_elem['href']
                    if not link.startswith('http'):
                        link = f"{self.base_url}{link}"
                    
                    # 获取视频封面
                    img_elem = item.select_one('img')
                    if not img_elem or 'src' not in img_elem.attrs:
                        logger.warning("未找到视频封面元素")
                        continue
                    cover = img_elem['src']
                    if not cover.startswith('http'):
                        cover = f"{self.base_url}{cover}"
                    
                    # 获取视频信息
                    info_elem = item.select_one('.meta')
                    info = info_elem.text.strip() if info_elem else ""
                    
                    # 获取视频ID
                    video_id = link.split('/')[-1] if link else ""
                    
                    result.append({
                        'title': title,
                        'link': link,
                        'cover': cover,
                        'info': info,
                        'id': video_id
                    })
                except Exception as e:
                    logger.error(f"解析视频项失败: {str(e)}")
                    continue
            
            return result
        except Exception as e:
            logger.error(f"解析页面数据失败: {str(e)}")
            return [] 