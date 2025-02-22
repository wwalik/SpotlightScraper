import requests
import threading
import re#gex

# Handles the metadata associated with a downloaded image if the use_metadata attribute is True
class ImageMetaData:
    title: str
    date: str
    src: str  

from concurrent.futures import ThreadPoolExecutor, Future
from collections.abc import MutableSequence, Callable
class ImageDownloader:
    # Thread pool attributes
    __threadpool: ThreadPoolExecutor
    __n_tasks: int
    __n_tasks_lock: threading.Lock
    
    # Information meant for the user of the class
    n_threads: int
    active_threads_progress: MutableSequence[float] # % progress
    imgs_metadata: MutableSequence[ImageMetaData] # history of downloaded images
    
    # Attributes set by caller
    url: str
    http_headers: dict[str, str]
    use_metadata: bool
    img_path_format_str: str
    directory: str
    request_timeout: int
    block_size: int
    
    def __init__(self, url, http_headers, use_metadata: bool=True, img_path_format_str: str='%t', directory: str='./imgs/', n_threads: int=None, request_timeout_seconds=5, block_size=4096):
        self.__threadpool = ThreadPoolExecutor(n_threads)
        self.n_threads = self.__threadpool._max_workers # if n_threads was None, this will find the actual number of threads
        self.__n_tasks_lock = threading.Lock()
        self.__n_tasks = 0
        self.active_threads_progress = [0.0] * self.n_threads
        
        if use_metadata:
            self.imgs_metadata = []
        else:
            self.imgs_metadata = None
        
        self.url = url
        self.use_metadata = use_metadata
        self.img_path_format_str = img_path_format_str
        self.directory = directory
        self.http_headers = http_headers
        self.request_timeout = request_timeout_seconds
        self.block_size = block_size
        
        self.__chdir(directory)
        
    
    @property
    def qsize(self):
        return self.__threadpool._work_queue.qsize()
    """Change the directory to which images will be downloaded to path"""
    def __chdir(self, path: str):
        from os import makedirs, chdir
        makedirs(path, exist_ok=True)
        chdir(path)
        self.directory = path
    
    
    """Keeps calling the looping_function until all tasks are completed"""
    def loop(self, looping_function: Callable) -> None:
        while self.__n_tasks != 0:
            looping_function(self)
    """"Blocks until all tasks in the queue are completed"""
    def wait(self) -> None:
        self.loop(lambda _: None)
    """Stop downloading"""
    def stop(self) -> None:
        self.__threadpool.shutdown(wait=False, cancel_futures=True)
    
    """Add a task to the threadpool"""
    def __queue_task(self, callback: Callable, task, **task_args) -> None:
        self.__n_tasks_lock.acquire()
        self.__n_tasks += 1
        self.__n_tasks_lock.release()
        
        future = self.__threadpool.submit(task, **task_args)
        future.add_done_callback(callback)
        future.add_done_callback(self.__finished_task)
    """Update the n_tasks when a task has finished"""
    def __finished_task(self, _) -> None:
        self.__n_tasks_lock.acquire()
        self.__n_tasks -= 1
        self.__n_tasks_lock.release()


    """Download all images of the page specified with page_id"""
    def download_page(self, page_id: int) -> None:
        parameters = {'url':f'{self.url}/{page_id}', 'headers':self.http_headers, 'timeout':self.request_timeout}
        self.__queue_task(self.__handle_page, requests.get, **parameters)
    """Callback for self.download_page"""
    def __handle_page(self, future: Future) -> None:
        from bs4 import BeautifulSoup
        response: requests.Response = future.result()
        response.raise_for_status()
        
        page_id = response.url[-1]
        # server transforms *.com/page/1 into *.com
        if page_id == 'm':
            page_id = 1

        soup = BeautifulSoup(response.content, 'html.parser')
        
        img_count = 0
        if self.use_metadata:
            links = soup.find_all('a', {'class': 'anons-thumbnail show'})
            for link in links:
                img_url = link['href']
                self.download_img_and_metadata(img_url, self.img_path_format_str)
                img_count += 1
        else:
            imgs = soup.find_all('img', {'class': 'thumbnail wp-post-image'})
            for img in imgs:
                img_src = img['src']
                img_src = re.sub(r'-\d+x\d+', '', img_src)
                
                
                img_path = f'{page_id}p{img_count}i'
                
                self.download_img(img_src, img_path)
                img_count += 1
        
    
    """downloads an image from its src url"""
    def download_img(self, img_src: str, img_path: str) -> None:
        parameters = {'img_src':img_src, 'img_path':img_path}
        self.__queue_task(lambda _: None, self.__blocks_download_img, **parameters)
    """Threaded function for downloading images and saving them to disk"""
    def __blocks_download_img(self, img_src: str, img_path: str) -> None:
        from math import ceil
        thread_id = int(re.findall(r'_(\d+)$', threading.current_thread().name)[0])
        try:
            self.active_threads_progress[thread_id] = 0.0 # TODO Thread safe?
            
            img_response = requests.get(img_src, headers=self.http_headers, timeout=self.request_timeout, stream=True)
            img_response.raise_for_status()
            
            content_length = int(img_response.headers['content-length'])
            n_blocks = ceil(content_length / self.block_size)

            format_extension = re.findall(r'.\w+$', img_src)[-1]
            img_path = img_path + format_extension
            with open(img_path, 'wb') as f:
                for block in img_response.iter_content(chunk_size=self.block_size):
                    f.write(block)
                    progress_increment = 100 / n_blocks
                    self.active_threads_progress[thread_id] += progress_increment
                f.close()
        except Exception as e:
            ImageDownloader.__handle_thread_exception(thread_id, e)


    """"One more GET request than download_img but gets more info"""
    def download_img_and_metadata(self, img_url: str, img_path_format: str):
        parameters = {'img_url': img_url, 'img_path_format': img_path_format}
        self.__queue_task(lambda _:None, self.__blocks_download_img_and_metadata, **parameters)
    """Similar to __blocks_download_img but also downloads the metadata and add it to the history"""
    def __blocks_download_img_and_metadata(self, img_url: int, img_path_format: str) -> ImageMetaData:
        from bs4 import BeautifulSoup
        thread_id = int(threading.current_thread().name[-1])
        
        try:
            page_response = requests.get(img_url, headers=self.http_headers, timeout=self.request_timeout)
            page_response.raise_for_status()
            
            # Fill metadata
            metadata = ImageMetaData()
            soup = BeautifulSoup(page_response.content, 'html.parser')
            imgs = soup.find_all('img', {'fetchpriority': 'high'})
            if len(imgs) != 1:
                raise Exception('More than 1 <img fetch-priority="high"> found in page!!!')
            metadata.title = imgs[0]['title']
            metadata.src = imgs[0]['src']
            metadata.src = re.sub(r'-\d+x\d+', '', metadata.src) # remove specific resolution
            
            date_spans = soup.find_all('span', {'class': 'date'})
            if len(date_spans) != 1:
                raise Exception('More than 1 <span class="date"> found in page!!!')
            metadata.date = date_spans[0].contents[0] #???? TODO
            
            self.imgs_metadata.append(metadata)
            
            
            # Format input string using image metadata
            # TODO: better formatting && BUG race condition if multiple files have the same name
            img_path_format = img_path_format.replace(r'%t', metadata.title)
            img_path_format = img_path_format.replace(r'%d', metadata.date)
            self.__blocks_download_img(metadata.src, img_path_format)
        except Exception as e:
            ImageDownloader.__handle_thread_exception(thread_id, e)    

    """Static function for handling exceptions that occur inside threads""" 
    def __handle_thread_exception(thread_id: int, e: Exception):
        message = f'---\nException in thread {thread_id}:\n\t{e}\n---\n'
        with open(f'../log_thread{thread_id}.txt', 'a+') as f:
            f.write(message)
            f.close()
            

