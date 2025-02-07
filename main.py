from image_downloader import ImageDownloader
import time

URL = 'https://windows10spotlight.com/page/' # + page number
N_THREADS = 10
# dummy User-Agent to avoid 403
HEADERS = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'}

def main():
    imgd = ImageDownloader(URL, HEADERS, use_metadata=False, img_path_format_str=r'%d_%t')
    
    n_pages = 10
    for i in range(1, n_pages+1):
        imgd.download_page(i)
    
    imgd.wait()


if __name__ == '__main__':
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(str(elapsed_time) + 's')    
