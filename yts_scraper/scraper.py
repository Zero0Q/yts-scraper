import os
import sys
import math
import json
import csv
import pickle
from datetime import datetime, timedelta
from concurrent.futures.thread import ThreadPoolExecutor
import requests
from tqdm import tqdm
from fake_useragent import UserAgent

class Scraper:
    """
    Scraper class.

    Must be initialized with args from argparser
    """
    # Constructor
    def __init__(self, args):
        self.output = args.output
        self.genre = args.genre
        self.minimum_rating = args.rating
        self.quality = '3D' if (args.quality == '3d') else args.quality
        self.categorize = args.categorize_by
        self.sort_by = args.sort_by
        self.year_limit = args.year_limit
        self.page_arg = args.page
        self.poster = args.background
        self.imdb_id = args.imdb_id
        self.multiprocess = args.multiprocess
        self.csv_only = args.csv_only
        
        # Auto-continue parameter for automated environments (GitHub Actions, etc.)
        self.auto_continue = getattr(args, 'auto_continue', False)

        self.movie_count = None
        self.url = None
        self.existing_file_counter = None
        self.skip_exit_condition = None
        self.downloaded_movie_ids = None
        self.pbar = None

        # Cache system for persistent tracking
        self.cache_file = os.path.join(os.path.dirname(__file__), 'scraper_cache.json')
        self.processed_movies_cache = self._load_cache()

        # Set output directory
        if args.output:
            if not args.csv_only:
                os.makedirs(self.output, exist_ok=True)
            self.directory = os.path.join(os.path.curdir, self.output)
        else:
            if not args.csv_only:
                os.makedirs(self.categorize.title(), exist_ok=True)
            self.directory = os.path.join(os.path.curdir, self.categorize.title())


        # Args for downloading in reverse chronological order
        if args.sort_by == 'latest':
            self.sort_by = 'date_added'
            self.order_by = 'desc'
        else:
            self.order_by = 'asc'


        # YTS API has a limit of 50 entries
        self.limit = 50

    def _load_cache(self):
        """Load the persistent cache of processed movies"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    
                # Clean old entries (older than 30 days to keep cache fresh)
                cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()
                cleaned_cache = {
                    movie_id: data for movie_id, data in cache_data.items()
                    if data.get('last_seen', '1900-01-01') > cutoff_date
                }
                
                print(f"Loaded cache with {len(cleaned_cache)} previously processed movies")
                return cleaned_cache
        except Exception as e:
            print(f"Warning: Could not load cache: {e}")
        
        return {}

    def _save_cache(self):
        """Save the persistent cache of processed movies"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.processed_movies_cache, f, indent=2)
            print(f"Saved cache with {len(self.processed_movies_cache)} processed movies")
        except Exception as e:
            print(f"Warning: Could not save cache: {e}")

    def _is_movie_cached(self, movie_id, movie_name, year, quality):
        """Check if a movie is already cached and up to date"""
        if movie_id not in self.processed_movies_cache:
            return False
            
        cached_movie = self.processed_movies_cache[movie_id]
        
        # Check if this specific quality was already processed
        cached_qualities = cached_movie.get('qualities', [])
        if quality in cached_qualities:
            print(f"Cache hit: {movie_name} ({year}) - {quality} already processed")
            return True
            
        return False

    def _cache_movie(self, movie_id, movie_name, year, quality, status='processed'):
        """Add movie to cache"""
        if movie_id not in self.processed_movies_cache:
            self.processed_movies_cache[movie_id] = {
                'name': movie_name,
                'year': year,
                'qualities': [],
                'first_seen': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            }
        
        # Update last seen and add quality if not already present
        self.processed_movies_cache[movie_id]['last_seen'] = datetime.now().isoformat()
        if quality not in self.processed_movies_cache[movie_id]['qualities']:
            self.processed_movies_cache[movie_id]['qualities'].append(quality)

    def _make_request_with_retry(self, url, headers, max_retries=3, timeout=15):
        """Make HTTP request with retry logic and exponential backoff"""
        import time
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=timeout, verify=True, headers=headers)
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 2  # Exponential backoff: 2s, 4s, 8s
                    tqdm.write(f'⏳ Request timeout (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...')
                    time.sleep(wait_time)
                    continue
                else:
                    tqdm.write(f'❌ Max retries exceeded for URL: {url}')
                    raise
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 3  # Longer wait for connection errors
                    tqdm.write(f'🔌 Connection error (attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s...')
                    time.sleep(wait_time)
                    continue
                else:
                    tqdm.write(f'❌ Connection failed after {max_retries} attempts')
                    raise
            except requests.exceptions.RequestException as e:
                tqdm.write(f'❌ Request error: {e}')
                raise

    # Connect to API and extract initial data
    def __get_api_data(self):
        # Formatted URL string
        url = '''https://yts.mx/api/v2/list_movies.json?quality={quality}&genre={genre}&minimum_rating={minimum_rating}&sort_by={sort_by}&order_by={order_by}&limit={limit}&page='''.format(
            quality=self.quality,
            genre=self.genre,
            minimum_rating=self.minimum_rating,
            sort_by=self.sort_by,
            order_by=self.order_by,
            limit=self.limit
        )

        # Generate random user agent header
        try:
            user_agent = UserAgent()
            headers = {'User-Agent': user_agent.random}
        except:
            print('Error occurred during fake user agent generation.')

        # Exception handling for connection errors
        try:
            req = self._make_request_with_retry(url, headers)
        except Exception as e:
            print(f"Error during API request: {e}")
            sys.exit(0)

        # Exception handling for JSON decoding errors
        try:
            data = req.json()
        except json.decoder.JSONDecodeError:
            print('Could not decode JSON')


        # Adjust movie count according to starting page
        if self.page_arg == 1:
            movie_count = data.get('data').get('movie_count')
        else:
            movie_count = (data.get('data').get('movie_count')) - ((self.page_arg - 1) * self.limit)

        self.movie_count = movie_count
        self.url = url

    def __initialize_download(self):
        # Used for exit/continue prompt that's triggered after 10 existing files
        self.existing_file_counter = 0
        self.skip_exit_condition = False

        # YTS API sometimes returns duplicate objects and
        # the script tries to download the movie more than once.
        # IDs of downloaded movie is stored in this array
        # to check if it's been downloaded before
        self.downloaded_movie_ids = []

        # Calculate page count and make sure that it doesn't
        # get the value of 1 to prevent range(1, 1)
        if math.trunc(self.movie_count / self.limit) + 1 == 1:
            page_count = 2
        else:
            page_count = math.trunc(self.movie_count / self.limit) + 1

        range_ = range(int(self.page_arg), page_count)


        print('Initializing download with these parameters:\n')
        print('Directory:\t{}\nQuality:\t{}\nMovie Genre:\t{}\nMinimum Rating:\t{}\nCategorization:\t{}\nMinimum Year:\t{}\nStarting page:\t{}\nMovie posters:\t{}\nAppend IMDb ID:\t{}\nMultiprocess:\t{}\n'
              .format(
                  self.directory,
                  self.quality,
                  self.genre,
                  self.minimum_rating,
                  self.categorize,
                  self.year_limit,
                  self.page_arg,
                  str(self.poster),
                  str(self.imdb_id),
                  str(self.multiprocess)
                  )
             )

        if self.movie_count <= 0:
            print('Could not find any movies with given parameters')
            sys.exit(0)
        else:
            print('Query was successful.')
            print('Found {} movies. Download starting...\n'.format(self.movie_count))

        # Create progress bar
        self.pbar = tqdm(
            total=self.movie_count,
            position=0,
            leave=True,
            desc='Downloading',
            unit='Files'
            )

        # Multiprocess executor
        # Setting max_workers to None makes executor utilize CPU number * 5 at most
        executor = ThreadPoolExecutor(max_workers=None)

        for page in range_:
            url = '{}{}'.format(self.url, str(page))

            # Generate random user agent header
            try:
                user_agent = UserAgent()
                headers = {'User-Agent': user_agent.random}
            except:
                print('Error occurred during fake user agent generation.')

            # Send request to API with retry logic
            try:
                page_response = self._make_request_with_retry(url, headers)
                data = page_response.json()
                movies = data.get('data', {}).get('movies')
            except Exception as e:
                tqdm.write(f'⚠️  Failed to fetch page {page} after retries: {e}')
                tqdm.write(f'🔄 Continuing with next page...')
                continue

            # Movies found on current page
            if not movies:
                tqdm.write('Could not find any movies on this page.\n')
                continue

            if self.multiprocess:
                # Wrap tqdm around executor to update pbar with every process
                tqdm(
                    executor.map(self.__filter_torrents, movies),
                    total=self.movie_count,
                    position=0,
                    leave=True
                    )

            else:
                for movie in movies:
                    self.__filter_torrents(movie)

        self.pbar.close()
        print('Download finished.')


    # Determine which magnet links to collect
    def __filter_torrents(self, movie):
        movie_id = str(movie.get('id'))
        movie_rating = movie.get('rating')
        movie_genres = movie.get('genres') if movie.get('genres') else ['None']
        movie_name_short = movie.get('title')
        imdb_id = movie.get('imdb_code')
        year = movie.get('year')
        language = movie.get('language')
        yts_url = movie.get('url')

        if year < self.year_limit:
            return

        # Every torrent option for current movie
        torrents = movie.get('torrents')
        # Remove illegal file/directory characters
        movie_name = movie.get('title_long').translate({ord(i):None for i in "'/\:*?<>|"})

        # Used to track successful processing
        is_processing_successful = False

        if movie_id in self.downloaded_movie_ids:
            return

        # In case movie has no available torrents
        if torrents is None:
            tqdm.write('Could not find any torrents for {}. Skipping...'.format(movie_name))
            return

        bin_content_img = (requests.get(movie.get('large_cover_image'))).content if self.poster else None

        # Iterate through available torrent files
        for torrent in torrents:
            quality = torrent.get('quality')
            torrent_url = torrent.get('url')
            torrent_hash = torrent.get('hash')
            
            # Check cache before processing
            if self._is_movie_cached(movie_id, movie_name, year, quality):
                continue
            
            if self.categorize and self.categorize != 'rating':
                if self.quality == 'all' or self.quality == quality:
                    for genre in movie_genres:
                        path = self.__build_path(movie_name, movie_rating, quality, genre, imdb_id, year)
                        is_processing_successful = self.__save_magnet_info(torrent_hash, bin_content_img, path, movie_name, movie_id, quality, imdb_id, year)
            else:
                if self.quality == 'all' or self.quality == quality:
                    self.__log_csv(movie_id, imdb_id, movie_name_short, year, language, movie_rating, quality, yts_url, torrent_url)
                    path = self.__build_path(movie_name, movie_rating, quality, None, imdb_id, year)
                    is_processing_successful = self.__save_magnet_info(torrent_hash, bin_content_img, path, movie_name, movie_id, quality, imdb_id, year)

            if is_processing_successful and self.quality == 'all' or self.quality == quality:
                tqdm.write('Processed {} {}'.format(movie_name, quality.upper()))
                self.pbar.update()

    # Creates a file path for each download
    def __build_path(self, movie_name, rating, quality, movie_genre, imdb_id, year):
        if self.csv_only:
            return

        directory = self.directory

        # New organization: Movie.Name (year)/
        directory += '/' + movie_name + ' (' + str(year) + ')'

        os.makedirs(directory, exist_ok=True)

        if self.imdb_id:
            filename = '{}.{}-{}'.format(movie_name, quality, imdb_id)
        else:
            filename = '{}.{}'.format(movie_name, quality)

        path = os.path.join(directory, filename)
        return path

    # Save magnet link information instead of downloading .torrent files
    def __save_magnet_info(self, torrent_hash, bin_content_img, path, movie_name, movie_id, quality=None, imdb_id=None, year=None):
        if self.csv_only:
            return

        if self.existing_file_counter > 10 and not self.skip_exit_condition:
            self.__prompt_existing_files()

        # Check if magnet info file already exists
        magnet_file_path = path + '.magnet'
        if os.path.isfile(magnet_file_path):
            tqdm.write('{}: Magnet info already exists. Skipping...'.format(movie_name))
            self.existing_file_counter += 1
            # Still cache it as processed
            if quality:
                self._cache_movie(movie_id, movie_name, year, quality)
            return False

        # Create magnet link from hash
        magnet_link = f"magnet:?xt=urn:btih:{torrent_hash}&dn={movie_name.replace(' ', '+')}&tr=udp://open.demonii.com:1337&tr=udp://tracker.openbittorrent.com:80&tr=udp://tracker.coppersurfer.tk:6969&tr=udp://glotorrents.pw:6969/announce&tr=udp://tracker.opentrackr.org:1337/announce&tr=udp://torrent.gresille.org:80/announce&tr=udp://p4p.arenabg.com:1337&tr=udp://tracker.leechers-paradise.org:6969"

        # Save magnet link and metadata to file
        magnet_info = {
            'magnet_link': magnet_link,
            'hash': torrent_hash,
            'movie_name': movie_name,
            'year': year,
            'quality': quality,
            'imdb_id': imdb_id,
            'movie_id': movie_id,
            'created_at': datetime.now().isoformat()
        }

        with open(magnet_file_path, 'w') as magnet_file:
            json.dump(magnet_info, magnet_file, indent=2)

        # Save poster image if requested
        if self.poster and bin_content_img:
            with open(path + '.jpg', 'wb') as img_file:
                img_file.write(bin_content_img)

        self.downloaded_movie_ids.append(movie_id)
        if quality:
            self._cache_movie(movie_id, movie_name, year, quality)
        self.existing_file_counter = 0
        return True

    def __log_csv(self, id, imdb_id, name, year, language, rating, quality, yts_url, torrent_url):
        path = os.path.join(os.path.curdir, 'YTS-Scraper.csv')
        csv_exists = os.path.isfile(path)

        with open(path, mode='a') as csv_file:
            headers = ['YTS ID', 'IMDb ID', 'Movie Title', 'Year', 'Language', 'Rating', 'Quality', 'YTS URL', 'IMDb URL', 'Torrent URL']
            writer = csv.DictWriter(csv_file, delimiter=',', lineterminator='\n', quotechar='"', quoting=csv.QUOTE_ALL, fieldnames=headers)

            if not csv_exists:
                writer.writeheader()

            writer.writerow({'YTS ID': id,
                             'IMDb ID': imdb_id,
                             'Movie Title': name,
                             'Year': year,
                             'Language': language,
                             'Rating': rating,
                             'Quality': quality,
                             'YTS URL': yts_url,
                             'IMDb URL': 'https://www.imdb.com/title/' + imdb_id,
                             'Torrent URL': torrent_url
                            })



    # Is triggered when the script hits 10 consecutive existing files
    def __prompt_existing_files(self):
        if self.auto_continue:
            tqdm.write('Auto-continuing mode: Skipping prompt and continuing download...')
            self.existing_file_counter = 0
            self.skip_exit_condition = True
            return

        tqdm.write('Found 10 existing files in a row. Do you want to keep downloading? Y/N')
        exit_answer = input()

        if exit_answer.lower() == 'n':
            tqdm.write('Exiting...')
            sys.exit(0)
        elif exit_answer.lower() == 'y':
            tqdm.write('Continuing...')
            self.existing_file_counter = 0
            self.skip_exit_condition = True
        else:
            tqdm.write('Invalid input. Enter "Y" or "N".')

    def download(self):
        self.__get_api_data()
        self.__initialize_download()
        # Save cache after download completes
        self._save_cache()
