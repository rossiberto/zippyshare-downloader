# zipyshare-downloader
# fetcher.py

import asyncio
import aiohttp
import requests
import asyncio
import logging
import os
import zipfile
from typing import List, Dict
from pathlib import Path
from .utils import extract_archived_file, build_zipping_log, archive_zip
from .errors import FileExpired
from .parser import finalization_info, parse_info
from .file import File

__all__ = (
    'download', 'extract_info',
    'download_coro', 'extract_info_coro'
)

log = logging.getLogger(__name__)

def get_info(url) -> Dict[str, str]:
    """
    Get informations in Zippyshare url.
    """
    log.info('Grabbing required informations in %s' % url)
    log.debug('Establishing connection to Zippyshare.')
    r = requests.get(url)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        log.exception('Zippyshare send %s code' % r.status_code)
        raise e from None
    log.debug('Successfully established connection to Zippyshare.')
    log.debug('Checking if file is not expired')
    if 'File has expired and does not exist anymore on this server' in r.text:
        log.exception('File has expired and does not exist anymore')
        raise FileExpired('File has expired and does not exist anymore')
    log.debug('Checking if file is exist')
    if 'File does not exist on this server' in r.text:
        log.exception('File does not exist on this server')
        raise FileNotFoundError('File does not exist on this server')
    return finalization_info(parse_info(url, r.text))

async def get_info_coro(url) -> Dict[str, str]:
    """
    Get informations in Zippyshare url.

    Unlike `get_info()` when you have to call `finalization_info()` manually
    to fix incorrect informations.
    This function automatically called it.
    """
    log.info('Grabbing required informations in %s' % url)
    log.debug('Establishing connection to Zippyshare.')
    async with aiohttp.ClientSession() as session:
        r = await session.get(url)
        try:
            r.raise_for_status()
        except aiohttp.ClientResponseError as e:
            log.exception('Zippyshare send %s code' % r.status)
            raise e from None
        body_html = await r.text()
        log.debug('Successfully established connection to Zippyshare.')
        log.debug('Checking if file is not expired')
        if 'File has expired and does not exist anymore on this server' in body_html:
            log.exception('File has expired and does not exist anymore')
            raise FileExpired('File has expired and does not exist anymore')
        log.debug('Checking if file is exist')
        if 'File does not exist on this server' in body_html:
            log.exception('File does not exist on this server')
            raise FileNotFoundError('File does not exist on this server')
        return await finalization_info(parse_info(url, body_html), True, session)

def download(*urls, zip: str=None, unzip: bool=False, **kwargs) -> List[File]:
    """
    Download multiple zippyshare urls

    Parameters
    -----------
    *urls
        Zippyshare urls.
    zip: :class:`str`
        Zip all downloaded files once finished.
        Zip filename will be taken from :param:`zip`,
        default to `None`.
        NOTE: You can't mix `zip` and `unzip` options together
        with value `True`, it will raise error.
    unzip: :class:`bool`
        Unzip all downloaded files once finished
        (if given file is zip format extract it, otherwise ignore it),
        default to `False`.
        NOTE: You can't mix `zip` and `unzip` options together
        with value `True`, it will raise error.
    **kwargs
        These parameters will be passed to `File.download()`,
        except for parameter `filename`.

    Returns
    -------
    List[:class:`File`]
        a list of Zippyshare files
    """
    if unzip and zip:
        raise ValueError("unzip and zip paramaters cannot be set together")
    downloaded_files = {}
    files = []
    for url in urls:
        info = finalization_info(get_info(url))
        file = File(info)
        files.append(file)
        if kwargs.get('filename') is not None:
            kwargs.pop('filename')
        file_path = file.download(**kwargs)
        downloaded_files[file] = file_path
        if unzip:
            extract_archived_file(str(file_path))
    if zip:
        log.info('Zipping all downloaded files')
        path = list(downloaded_files.values())[0]
        zip_path = (path.parent / zip)
        with zipfile.ZipFile(zip_path, 'w') as zip_writer:
            for file, path in downloaded_files.items():
                log.debug('Writing %s to %s' % (
                    path,
                    zip_path
                ))
                zip_writer.write(path)
                os.remove(path)
        log.info('Successfully zipped all downloaded files')
    return files

def extract_info(url: str, download: bool=True, unzip: bool=False, **kwargs) -> File:
    """
    Extract all informations in Zippyshare url.

    Parameters
    ------------
    url: :class:`str`
        Zippyshare url.
    download: :class:`bool`
        Download given zippyshare url if `True`, 
        default to `True`.
    unzip: :class:`bool`
        Unzip downloaded file once finished
        (if given file is zip or tar format extract it, otherwise ignore it),
        default to `False`.
    **kwargs
        These parameters will be passed to `File.download()`

    Returns
    -------
    :class:`File`
        Zippyshare file
    """
    info = finalization_info(get_info(url))
    file = File(info)
    if download:
        file_path = file.download(**kwargs)
        if unzip:
            extract_archived_file(str(file_path))
    return file

async def extract_info_coro(url: str, download: bool=True, unzip: bool=False, **kwargs) -> File:
    """
    Extract all informations in Zippyshare url.

    Parameters
    ------------
    url: :class:`str`
        Zippyshare url.
    download: :class:`bool`
        Download given zippyshare url if `True`, 
        default to `True`.
    unzip: :class:`bool`
        Unzip downloaded file once finished
        (if given file is zip or tar format extract it, otherwise ignore it),
        default to `False`.
    **kwargs
        These parameters will be passed to `File.download()`

    Returns
    -------
    :class:`File`
        Zippyshare file
    """
    def process_download(file, kwargs, unzip):
        file_path = file.download(**kwargs)
        if unzip:
            extract_archived_file(str(file_path))
    info = await get_info_coro(url)
    file = File(info)
    loop = asyncio.get_event_loop()
    if download:
        await loop.run_in_executor(None, lambda: process_download(file, kwargs, unzip))
    return file

async def download_coro(*urls, zip: str=None, unzip: bool=False, **kwargs) -> List[File]:
    """
    "Coroutine Function"

    Download multiple zippyshare urls

    Parameters
    -----------
    *urls: :class:`str`
        Zippyshare urls.
    zip: :class:`str`
        Zip all downloaded files once finished.
        Zip filename will be taken from :param:`zip`,
        default to ``None``.
        NOTE: You can't mix ``zip`` and ``unzip`` options together
        with value `True`, it will raise error.
    unzip: :class:`bool`
        Unzip all downloaded files once finished
        (if given file is zip format extract it, otherwise ignore it),
        default to ``False``.
        NOTE: You can't mix ``zip`` and ``unzip`` options together
        with value `True`, it will raise error.
    **kwargs
        These parameters will be passed to :meth:`File.download()`,
        except for parameter :param:`filename`.

    Returns
    -------
    List[:class:`File`]
        a list of Zippyshare files
    """
    if unzip and zip:
        raise ValueError("unzip and zip paramaters cannot be set together")
    loop = asyncio.get_event_loop()
    downloaded_files = {}
    files = []
    for url in urls:
        info = await get_info_coro(url)
        file = File(info)
        files.append(file)
        if kwargs.get('filename') is not None:
            kwargs.pop('filename')
        file_path = await file.download_coro(**kwargs)
        downloaded_files[file] = file_path
        def _unzip_worker(file_path):
            extract_archived_file(str(file_path))
        if unzip:
            await loop.run_in_executor(None, lambda: _unzip_worker(file_path))
    if zip:
        log.info(build_zipping_log(downloaded_files, 'Zipping all downloaded files to "%s"' % zip))
        await loop.run_in_executor(None, lambda: archive_zip(downloaded_files, zip))
        log.info(build_zipping_log(downloaded_files, 'Successfully zip all downloaded files to "%s"' % zip))
    return files