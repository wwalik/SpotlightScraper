from image_downloader import ImageDownloader
import time

URL = 'https://windows10spotlight.com/page/'
HEADERS = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'} # dummy User-Agent to avoid 403

def display_progress(imgd: ImageDownloader):
    from sys import stdout

    threads_per_row = 4
    # move cursor up n_threads lines
    stdout.write(f'\033[{int(imgd.n_threads / threads_per_row)+1}A')

    
    # loop over every active thread
    threads_drawn = 0
    for progress in imgd.active_threads_progress:
        progress = round(progress)

        # deletes current line and moves cursor to beginning
        print(f'{progress}  \t', end='')
        threads_drawn += 1
        if (threads_drawn % threads_per_row) == 0:
            print('')
            print("\033[2K\r", end='')

    print('Tasks in queue: ' + str(imgd.qsize))

        

def main():
    imgd = ImageDownloader(URL, HEADERS, n_threads=16, use_metadata=True)
    
    n_pages = 5
    for i in range(1, n_pages+1):
        imgd.download_page(i)
    

    print('\033[?25l', end="") # hide cursor
    print('\n' * 4)
    try:
        imgd.loop(display_progress)
    except KeyboardInterrupt:
        print('\n' * imgd.n_threads)
        print('^C detected... cleaning up!')
        imgd.stop()
    
    print('\033[?25h', end="") # show cursor


if __name__ == '__main__':
    start_time = time.time()
    main()
    elapsed_time = time.time() - start_time
    print(str(elapsed_time) + 's')    
