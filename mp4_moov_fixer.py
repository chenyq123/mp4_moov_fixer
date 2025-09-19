import os
import sys
import subprocess
import shutil
import requests
import zipfile
import time
from tqdm import tqdm
import argparse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext, messagebox
import threading

# 版本号常量
VERSION = "1.0.3"

class MP4MoovFixer:
    def __init__(self, input_dir=None, output_dir="processed_videos", log_callback=None, progress_callback=None, skip_detection=False):
        self.input_dir = input_dir if input_dir else os.getcwd()
        self.output_dir = os.path.join(self.input_dir, output_dir)
        self.ffmpeg_path = self._get_ffmpeg_path()
        self.log_callback = log_callback  # 用于UI日志更新的回调函数
        self.progress_callback = progress_callback  # 用于UI进度条更新的回调函数
        self.stop_flag = False  # 用于取消处理的标志
        self.skip_detection = skip_detection  # 是否跳过moov检测，直接全部转换
        self.log_entries = []  # 存储普通日志
        self.debug_log_entries = []  # 单独存储调试日志
    
    def _get_ffmpeg_path(self):
        """获取FFmpeg可执行文件路径"""
        # 优先使用系统环境变量中的ffmpeg
        ffmpeg_cmd = "ffmpeg" if sys.platform != "win32" else "ffmpeg.exe"
        if shutil.which(ffmpeg_cmd):
            return ffmpeg_cmd
            
        # 检查当前目录下是否有ffmpeg - 遍历所有子目录查找
        for root, dirs, files in os.walk(os.getcwd()):
            # 优先检查ffmpeg目录
            if "ffmpeg" in root.lower() and ffmpeg_cmd in files:
                ffmpeg_path = os.path.join(root, ffmpeg_cmd)
                # 确保文件有执行权限
                try:
                    os.chmod(ffmpeg_path, 0o755)
                except:
                    pass  # Windows系统可能不需要这一步
                return ffmpeg_path
                
        # 如果遍历未找到，检查特定路径
        common_paths = [
            os.path.join(os.getcwd(), "ffmpeg", ffmpeg_cmd),
            os.path.join(os.getcwd(), "ffmpeg", "bin", ffmpeg_cmd),
            os.path.join(os.getcwd(), "ffmpeg-*/bin", ffmpeg_cmd)
        ]
        
        for path_pattern in common_paths:
            # 处理通配符路径
            if "*" in path_pattern:
                import glob
                matches = glob.glob(path_pattern)
                if matches:
                    return matches[0]
            elif os.path.exists(path_pattern):
                return path_pattern
                
        return None
    
    def _download_ffmpeg(self):
        """下载并解压FFmpeg"""
        self._log("FFmpeg未找到，正在下载...")
        
        # 根据操作系统选择下载链接
        if sys.platform == "win32":
            url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            extract_dir = os.path.join(os.getcwd(), "ffmpeg")
        elif sys.platform == "darwin":
            url = "https://evermeet.cx/ffmpeg/getrelease/darwin64/static/ffmpeg"
            extract_dir = os.path.join(os.getcwd(), "ffmpeg", "bin")
        else:  # Linux
            self._log("Linux系统，请手动安装FFmpeg: sudo apt-get install ffmpeg")
            sys.exit(1)
        
        # 创建下载目录
        try:
            os.makedirs(extract_dir, exist_ok=True)
        except Exception as e:
            self._log(f"创建目录失败: {e}")
            return False
        
        # 下载文件
        try:
            if sys.platform == "win32":
                zip_path = os.path.join(extract_dir, "ffmpeg.zip")
                
                # 检查是否有进度回调函数，如果有则使用GUI进度条，否则使用命令行进度条
                with requests.get(url, stream=True) as r:
                    total_size = int(r.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    # 确保文件可以正确打开
                    with open(zip_path, 'wb') as f:
                        # 根据是否有GUI回调决定使用哪种进度更新方式
                        if self.progress_callback:
                            # GUI模式：使用回调函数更新进度
                            self._log(f"开始下载FFmpeg ({total_size/1024/1024:.2f} MB)...")
                            for data in r.iter_content(chunk_size=8192):  # 使用更大的块大小提高下载效率
                                if self.stop_flag:
                                    return False
                                size = f.write(data)
                                downloaded_size += size
                                # 更新进度
                                if total_size > 0:
                                    progress_percent = (downloaded_size / total_size) * 100
                                    self.progress_callback(progress_percent, f"正在下载FFmpeg: {downloaded_size/1024/1024:.2f} MB/{total_size/1024/1024:.2f} MB")
                        else:
                            # 命令行模式：使用tqdm进度条
                            with tqdm(
                                desc="下载FFmpeg",
                                total=total_size,
                                unit='iB',
                                unit_scale=True,
                                unit_divisor=1024,
                            ) as pbar:
                                for data in r.iter_content(chunk_size=8192):
                                    if self.stop_flag:
                                        return False
                                    size = f.write(data)
                                    pbar.update(size)
                
                # 解压文件
                self._log("正在解压FFmpeg...")
                if self.progress_callback:
                    self.progress_callback(90, "正在解压FFmpeg...")
                
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # 删除zip文件
                os.remove(zip_path)
                
                # 查找ffmpeg.exe所在的bin目录
                found = False
                for root, dirs, files in os.walk(extract_dir):
                    if "ffmpeg.exe" in files:
                        self.ffmpeg_path = os.path.join(root, "ffmpeg.exe")
                        # 确保文件有执行权限
                        try:
                            os.chmod(self.ffmpeg_path, 0o755)
                        except:
                            # Windows系统可能不需要这一步
                            pass
                        found = True
                        break
                
                if not found:
                    self._log("解压后未找到ffmpeg.exe")
                    return False
                
            else:  # macOS
                ffmpeg_path = os.path.join(extract_dir, "ffmpeg")
                
                with requests.get(url, stream=True) as r:
                    total_size = int(r.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(ffmpeg_path, 'wb') as f:
                        if self.progress_callback:
                            self._log(f"开始下载FFmpeg ({total_size/1024/1024:.2f} MB)...")
                            for data in r.iter_content(chunk_size=8192):
                                if self.stop_flag:
                                    return False
                                size = f.write(data)
                                downloaded_size += size
                                if total_size > 0:
                                    progress_percent = (downloaded_size / total_size) * 100
                                    self.progress_callback(progress_percent, f"正在下载FFmpeg: {downloaded_size/1024/1024:.2f} MB/{total_size/1024/1024:.2f} MB")
                        else:
                            with tqdm(
                                desc="下载FFmpeg",
                                total=total_size,
                                unit='iB',
                                unit_scale=True,
                                unit_divisor=1024,
                            ) as pbar:
                                for data in r.iter_content(chunk_size=8192):
                                    if self.stop_flag:
                                        return False
                                    size = f.write(data)
                                    pbar.update(size)
                
                # 确保文件有执行权限
                os.chmod(ffmpeg_path, 0o755)
                self.ffmpeg_path = ffmpeg_path
                
            self._log(f"FFmpeg下载完成: {self.ffmpeg_path}")
            if self.progress_callback:
                self.progress_callback(100, "FFmpeg下载完成")
            return True
        except Exception as e:
            self._log(f"FFmpeg下载失败: {str(e)}")
            # 确保输出详细的错误信息
            import traceback
            self._log(f"错误详情: {traceback.format_exc()}")
            return False
    
    def _fix_moov_position(self, input_file, output_file):
        """使用FFmpeg将moov原子移到文件开头"""
        try:
            self._log(f"开始修复moov原子位置: {os.path.basename(input_file)}", "DEBUG")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # 使用更健壮的命令执行方式
            cmd = [self.ffmpeg_path, "-i", input_file, "-c", "copy", "-movflags", 
                   "+faststart", "-y", output_file]
            
            # 添加creationflags参数以避免在Windows上弹出黑框
            kwargs = {'check': False, 'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
            if sys.platform == 'win32':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
            self._log(f"执行ffmpeg命令: {' '.join(cmd)}", "DEBUG")
            
            # 添加超时处理
            try:
                result = subprocess.run(cmd, timeout=120, **kwargs)
                
                # 记录命令执行结果和错误信息
                self._log(f"ffmpeg命令退出码: {result.returncode}", "DEBUG")
                # 检查命令是否执行成功
                if result.returncode != 0:
                    if result.stderr:
                        stderr_content = result.stderr.decode('utf-8', errors='ignore')
                        # 错误时输出更多的ffmpeg日志内容
                        self._log(f"ffmpeg命令执行失败，退出码: {result.returncode}", "ERROR")
                    self._log(f"ffmpeg错误输出: {stderr_content[:500]}", "ERROR")
                    return False
                
            except subprocess.TimeoutExpired:
                self._log(f"ffmpeg处理超时: {os.path.basename(input_file)}", "ERROR")
                # 删除可能残留的输出文件
                if os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                    except:
                        pass
                return False
            
            # 检查转换后视频的大小
            if os.path.exists(output_file):
                input_size = os.path.getsize(input_file)
                output_size = os.path.getsize(output_file)
                
                # 确保输出文件不为空
                if output_size == 0:
                    self._log(f"警告：转换后文件为空 {input_file}", "WARNING")
                    try:
                        os.remove(output_file)
                    except:
                        pass
                    return False
                
                size_diff_percent = abs(input_size - output_size) / input_size * 100
                
                # 如果输出文件大小与输入文件相差超过10%，视为转换失败
                if size_diff_percent > 10:
                    self._log(f"警告：转换后文件大小异常 {input_file}")
                    self._log(f"  - 原始大小: {input_size/1024/1024:.2f} MB")
                    self._log(f"  - 转换后大小: {output_size/1024/1024:.2f} MB")
                    self._log(f"  - 差异: {size_diff_percent:.2f}%")
                    
                    # 删除可能损坏的输出文件
                    try:
                        os.remove(output_file)
                        self._log(f"已删除可能损坏的输出文件: {output_file}")
                    except Exception as del_err:
                        self._log(f"无法删除可能损坏的输出文件 {output_file}: {del_err}")
                    return False
                else:
                    self._log(f"文件大小校验通过: {os.path.basename(input_file)}")
                    self._log(f"  - 原始大小: {input_size/1024/1024:.2f} MB, 转换后: {output_size/1024/1024:.2f} MB")
            else:
                self._log(f"警告：转换后文件不存在 {input_file}", "WARNING")
                return False
            
            return True
        except Exception as e:
            self._log(f"处理文件失败 {input_file}: {str(e)}", "ERROR")
            # 输出详细的错误信息
            import traceback
            self._log(f"错误详情: {traceback.format_exc()}", "DEBUG")
            # 删除可能残留的输出文件
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                    self._log(f"已删除残留的输出文件: {output_file}")
                except Exception as del_err:
                    self._log(f"无法删除残留的输出文件 {output_file}: {del_err}")
            return False
    
    def _check_needs_processing(self, mp4_file):
        """检查MP4文件是否需要处理（moov原子是否已经在文件开头）"""
        try:
            self._log(f"开始检查文件: {os.path.basename(mp4_file)}", "DEBUG")
            
            # 检查是否存在ffprobe可执行文件（ffprobe通常与ffmpeg在同一目录）
            ffprobe_path = os.path.join(os.path.dirname(self.ffmpeg_path), "ffprobe.exe" if sys.platform == 'win32' else "ffprobe")
            use_ffprobe = os.path.exists(ffprobe_path)
            self._log(f"ffprobe路径: {ffprobe_path}, 是否存在: {use_ffprobe}", "DEBUG")
            
            # 优先使用ffprobe进行检测，因为它专门用于分析媒体文件
            if use_ffprobe:
                try:
                    self._log(f"使用ffprobe进行检测", "DEBUG")
                    # 使用ffprobe trace模式获取详细的原子信息，与用户命令行方式一致
                    cmd = [ffprobe_path, "-v", "trace", "-i", mp4_file]
                    kwargs = {'capture_output': True, 'text': True}
                    if sys.platform == 'win32':
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    
                    self._log(f"执行ffprobe命令: {' '.join(cmd)}", "DEBUG")
                    
                    # 使用更健壮的命令执行方式，增加超时和重试机制
                    try:
                        result = subprocess.run(cmd, timeout=30, **kwargs)
                    except subprocess.TimeoutExpired:
                        self._log(f"ffprobe命令执行超时，尝试使用简化参数", "WARNING")
                        # 使用更简单的参数进行重试
                        cmd = [ffprobe_path, "-show_format", "-show_streams", "-i", mp4_file]
                        result = subprocess.run(cmd, timeout=15, **kwargs)
                    
                    # 尝试从stdout和stderr都获取输出
                    ffprobe_output = (result.stdout or "") + (result.stderr or "")
                    
                    # 输出部分ffprobe结果用于调试
                    debug_output = ffprobe_output[:500] if len(ffprobe_output) > 500 else ffprobe_output
                    self._log(f"ffprobe输出前500字符: {debug_output}", "DEBUG")
                    self._log(f"ffprobe输出长度: {len(ffprobe_output)}字符", "DEBUG")
                    
                    # 如果ffprobe输出为空，尝试直接读取文件二进制内容来检测moov位置
                    if not ffprobe_output.strip():
                        self._log(f"ffprobe未返回输出，尝试直接分析文件结构", "WARNING")
                        # 使用文件系统方法检查文件末尾是否包含moov原子
                        try:
                            file_size = os.path.getsize(mp4_file)
                            # 读取文件末尾的部分内容进行快速检查
                            with open(mp4_file, 'rb') as f:
                                f.seek(max(0, file_size - 1024 * 10))  # 读取最后10KB
                                end_data = f.read()
                            # 检查是否包含moov原子标识
                            if b'moov' in end_data:
                                self._log(f"文件尾部检测到moov原子，需要处理: {os.path.basename(mp4_file)}", "INFO")
                                return True
                        except Exception as e:
                            self._log(f"直接分析文件结构失败: {str(e)}", "DEBUG")
                    
                    # 分析ffprobe输出，寻找moov原子的偏移量信息
                    # 用户命令行输出示例：[mov,mp4,m4a,3gp,3g2,mj2 @ 000002f9338a3700] type:'moov' parent:'root' sz: 18822 41660193 41679007
                    import re
                    # 增强正则表达式，匹配更多可能的格式变化
                    moov_patterns = [
                        r"type:'moov' parent:'root' sz: (\d+) (\d+) (\d+)",
                        r"type:\s*'moov'\s+parent:\s*'root'\s+sz:\s+(\d+)\s+(\d+)\s+(\d+)",
                        r"moov\s+\(offset: (\d+), size: (\d+)\)",
                        r"moov\s+atom\s+at\s+position\s+(\d+)",
                        r"moov\s+at\s+offset\s+(\d+)",
                        r"moov\s+size\s+(\d+)\s+offset\s+(\d+)"
                    ]
                    
                    found_match = False
                    for pattern in moov_patterns:
                        moov_matches = re.finditer(pattern, ffprobe_output)
                        for match in moov_matches:
                            found_match = True
                            try:
                                # 根据不同的正则表达式匹配结果进行处理
                                if len(match.groups()) == 3:
                                    atom_size = int(match.group(1))
                                    moov_offset = int(match.group(2))
                                    file_size = int(match.group(3))
                                elif len(match.groups()) == 2:
                                    moov_offset = int(match.group(1))
                                    atom_size = int(match.group(2))
                                    file_size = os.path.getsize(mp4_file)
                                else:
                                    moov_offset = int(match.group(1))
                                    atom_size = 0
                                    file_size = os.path.getsize(mp4_file)
                                
                                self._log(f"匹配到moov原子信息: size={atom_size}, offset={moov_offset}, file_size={file_size}", "DEBUG")
                                
                                # 计算moov原子相对于文件大小的位置百分比
                                moov_position_percent = (moov_offset / file_size) * 100
                                self._log(f"moov原子位置百分比: {moov_position_percent:.2f}%", "DEBUG")
                                
                                # 如果moov原子位于文件的90%之后，认为是后置的
                                if moov_position_percent > 90:
                                    self._log(f"ffprobe检测到moov在文件尾部（偏移量: {moov_offset}, 文件大小: {file_size}）: {os.path.basename(mp4_file)}", "INFO")
                                    return True
                                # 如果moov原子位于文件的10%之前，认为是前置的
                                elif moov_position_percent < 10:
                                    self._log(f"ffprobe检测到moov在文件开头: {os.path.basename(mp4_file)}", "INFO")
                                    return False
                            except Exception as e:
                                self._log(f"解析moov原子信息时出错: {str(e)}", "DEBUG")
                                continue
                    
                    if not found_match:
                        self._log(f"未找到moov原子的偏移量信息，尝试其他方法", "DEBUG")
                        
                        # 检查输出中是否有mdat出现在moov之前的线索
                        if "mdat" in ffprobe_output and "moov" in ffprobe_output:
                            mdat_pos = ffprobe_output.find("mdat")
                            moov_pos = ffprobe_output.find("moov")
                            self._log(f"mdat位置: {mdat_pos}, moov位置: {moov_pos}", "DEBUG")
                            if mdat_pos < moov_pos:
                                self._log(f"ffprobe输出中mdat先于moov出现，文件需要处理: {os.path.basename(mp4_file)}", "INFO")
                                return True
                        else:
                            self._log(f"ffprobe输出中未同时找到mdat和moov关键词", "DEBUG")
                    
                    # 检查encoder信息作为补充
                    self._log(f"尝试检查encoder信息", "DEBUG")
                    cmd_encoder = [ffprobe_path, "-v", "error", "-show_entries", "format_tags=encoder", "-of", "default=noprint_wrappers=1:nokey=1", mp4_file]
                    self._log(f"执行encoder检查命令: {' '.join(cmd_encoder)}", "DEBUG")
                    result_encoder = subprocess.run(cmd_encoder, **kwargs)
                    encoder_info = (result_encoder.stdout or "").strip().lower()
                    self._log(f"encoder信息: '{encoder_info}'", "DEBUG")
                    if "faststart" in encoder_info:
                        self._log(f"ffprobe检测到faststart格式: {os.path.basename(mp4_file)}", "INFO")
                        return False
                except Exception as e:
                    self._log(f"ffprobe检测失败: {str(e)}", "DEBUG")
                    # ffprobe检测失败，回退到ffmpeg方式
                    pass
            
            # 使用ffmpeg trace模式作为备选方法
            self._log(f"ffprobe检测未成功，使用ffmpeg trace模式", "DEBUG")
            cmd = [self.ffmpeg_path, "-v", "trace", "-i", mp4_file]
            kwargs = {'capture_output': True, 'text': True}
            if sys.platform == 'win32':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            
            self._log(f"执行ffmpeg命令: {' '.join(cmd)}", "DEBUG")
            result = subprocess.run(cmd, **kwargs)
            stderr_output = result.stderr or ""  # 确保stderr_output不是None
            self._log(f"ffmpeg输出长度: {len(stderr_output)}字符", "DEBUG")
            
            # 检查是否已经是faststart格式 - 支持多种可能的关键词
            faststart_keywords = [
                "moov atom is before mdat atom",
                "moov before mdat",
                "moov found at beginning",
                "moov at start",
                "faststart enabled",
                "moov placed at front"
            ]
            
            # 检查是否需要处理 - 支持多种可能的关键词
            needs_processing_keywords = [
                "mdat atom is before moov atom",
                "moov after mdat",
                "moov found at end",
                "moov atom at the end",
                "moov atom is after mdat atom",
                "moov at end",
                "moov located after mdat",
                "moov comes after mdat",
                "moov last",
                "moov原子位于文件尾部",
                "需要faststart处理"
            ]
            
            self._log(f"使用关键词列表进行检测", "DEBUG")
            # 转为小写以实现大小写不敏感匹配
            stderr_lower = stderr_output.lower()
            
            # 输出部分stderr用于调试
            debug_stderr = stderr_lower[:500] if len(stderr_lower) > 500 else stderr_lower
            self._log(f"ffmpeg stderr前500字符(lower): {debug_stderr}", "DEBUG")
            
            # 检查是否已经是faststart格式
            for keyword in faststart_keywords:
                if keyword.lower() in stderr_lower:
                    self._log(f"匹配到faststart关键词 '{keyword}': {os.path.basename(mp4_file)}", "DEBUG")
                    self._log(f"文件已经是faststart格式: {os.path.basename(mp4_file)}", "INFO")
                    return False
            
            # 检查是否有moov在mdat之后的情况
            for keyword in needs_processing_keywords:
                if keyword.lower() in stderr_lower:
                    self._log(f"匹配到需要处理的关键词 '{keyword}': {os.path.basename(mp4_file)}", "DEBUG")
                    self._log(f"检测到moov在mdat之后: {os.path.basename(mp4_file)}", "INFO")
                    return True
            
            # 即使没有匹配到关键词，也检查mdat和moov在stderr中的出现顺序
            self._log(f"未匹配到特定关键词，检查mdat和moov出现顺序", "DEBUG")
            if "mdat" in stderr_lower and "moov" in stderr_lower:
                # 查找所有mdat和moov的出现位置，进行全面比较
                mdat_positions = []
                moov_positions = []
                
                # 查找所有mdat的位置
                pos = stderr_lower.find("mdat")
                while pos != -1:
                    mdat_positions.append(pos)
                    pos = stderr_lower.find("mdat", pos + 1)
                
                # 查找所有moov的位置
                pos = stderr_lower.find("moov")
                while pos != -1:
                    moov_positions.append(pos)
                    pos = stderr_lower.find("moov", pos + 1)
                
                self._log(f"ffmpeg stderr中mdat位置列表: {mdat_positions}", "DEBUG")
                self._log(f"ffmpeg stderr中moov位置列表: {moov_positions}", "DEBUG")
                
                # 检查是否存在mdat出现在moov之前的情况
                has_mdat_before_moov = False
                for mdat_pos in mdat_positions:
                    for moov_pos in moov_positions:
                        if mdat_pos < moov_pos:
                            has_mdat_before_moov = True
                            break
                    if has_mdat_before_moov:
                        break
                
                if has_mdat_before_moov:
                    self._log(f"ffmpeg输出中发现mdat先于moov出现的情况，文件需要处理: {os.path.basename(mp4_file)}", "INFO")
                    return True
            
            self._log(f"未匹配到任何关键词，尝试文件大小比较方法", "DEBUG")
            
            # 使用更直接的方法：尝试用faststart选项处理文件
            self._log(f"尝试使用faststart处理并比较文件大小", "DEBUG")
            # 创建临时文件路径
            temp_output = os.path.join(os.path.dirname(mp4_file), f"temp_{os.path.basename(mp4_file)}")
            
            try:
                # 尝试应用faststart
                cmd = [self.ffmpeg_path, "-i", mp4_file, "-c", "copy", "-movflags", "+faststart", "-y", temp_output]
                # 添加creationflags参数以避免在Windows上弹出黑框
                kwargs = {'capture_output': True, 'text': True}
                if sys.platform == 'win32':
                    kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                
                self._log(f"执行faststart命令: {' '.join(cmd)}", "DEBUG")
                result = subprocess.run(cmd, **kwargs)
                
                # 记录命令执行结果
                self._log(f"faststart命令退出码: {result.returncode}", "DEBUG")
                if result.stderr:
                    self._log(f"faststart命令stderr输出长度: {len(result.stderr)}字符", "DEBUG")
                    self._log(f"faststart命令stderr前200字符: {result.stderr[:200]}", "DEBUG")
            
                # 比较文件大小
                if os.path.exists(temp_output):
                    original_size = os.path.getsize(mp4_file)
                    processed_size = os.path.getsize(temp_output)
                    size_diff_percent = abs(original_size - processed_size) / original_size * 100
                    
                    self._log(f"原文件大小: {original_size} bytes, 处理后大小: {processed_size} bytes, 差异: {size_diff_percent:.2f}%", "DEBUG")
                    
                    # 删除临时文件
                    try:
                        os.remove(temp_output)
                        self._log(f"已删除临时文件: {temp_output}", "DEBUG")
                    except Exception as e:
                        self._log(f"删除临时文件失败: {str(e)}", "WARNING")
                    
                    # 如果处理前后文件大小差异超过1%，说明文件结构有变化，需要处理
                    if size_diff_percent > 1:
                        self._log(f"文件结构需要优化 (大小差异 {size_diff_percent:.2f}%): {os.path.basename(mp4_file)}", "INFO")
                        return True
                    else:
                        self._log(f"文件大小差异较小 ({size_diff_percent:.2f}%), 可能已经是最优格式: {os.path.basename(mp4_file)}", "DEBUG")
                else:
                    self._log(f"临时文件不存在，faststart处理可能失败", "WARNING")
            except Exception as e:
                self._log(f"执行faststart命令时出错: {str(e)}", "WARNING")
                
            # 最后的保障措施：检查文件大小和扩展名
            file_size = os.path.getsize(mp4_file)
            is_mp4 = mp4_file.lower().endswith('.mp4')
            
            # 优先检查文件是否是MP4格式
            if not is_mp4:
                self._log(f"非MP4文件，跳过处理: {os.path.basename(mp4_file)}", "DEBUG")
                return False
            
            # 对于大于5MB的MP4文件，默认认为可能需要处理（更保守的策略）
            if file_size > 5 * 1024 * 1024:  # 从10MB降低到5MB，提高检测覆盖率
                self._log(f"大文件保障措施: 大于5MB的MP4文件默认处理: {os.path.basename(mp4_file)}", "INFO")
                return True
            
            # 对于所有MP4文件，无论大小，都尝试处理（最保守的策略）
            self._log(f"安全保障: 所有MP4文件都尝试进行moov前置处理: {os.path.basename(mp4_file)}", "DEBUG")
            return True
            
            # 所有检测都未匹配，返回不需要处理
            self._log(f"所有检测方法都未发现需要处理的情况: {os.path.basename(mp4_file)}", "DEBUG")
            return False
        except Exception as e:
            self._log(f"检查文件时出错: {str(e)}", "WARNING")
            return True  # 出错时默认需要处理
    
    def process_files(self):
        """处理所有MP4文件"""
        # 记录版本信息
        self._log(f"MP4 Moov Fixer 版本: {VERSION}", "INFO")
        
        # 检查并下载FFmpeg
        if not self.ffmpeg_path:
            if not self._download_ffmpeg():
                self._log("无法获取FFmpeg，程序退出", "ERROR")
                return False
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 获取所有MP4文件
        mp4_files = [f for f in os.listdir(self.input_dir) if f.lower().endswith('.mp4')]
        
        if not mp4_files:
            self._log("没有找到MP4文件", "WARNING")
            return True
        
        self._log(f"找到 {len(mp4_files)} 个MP4文件，开始处理...", "INFO")
        self._log("-" * 50)
        
        # 处理每个文件
        success_count = 0
        fail_count = 0
        skipped_count = 0
        
        for i, mp4_file in enumerate(mp4_files):
            if self.stop_flag:
                self._log("处理已取消", "WARNING")
                return False
            
            input_path = os.path.join(self.input_dir, mp4_file)
            output_path = os.path.join(self.output_dir, mp4_file)
            
            # 更新进度
            progress_percent = (i + 1) / len(mp4_files) * 100
            if self.progress_callback:
                self.progress_callback(progress_percent, f"处理中: {mp4_file}")
            
            # 文件处理开始标记
            self._log(f"开始处理文件 ({i+1}/{len(mp4_files)}): {mp4_file}", "INFO")
            
            # 检查是否跳过检测
            if self.skip_detection:
                # 跳过检测，直接全部转换
                self._log(f"  - 状态: 跳过moov检测，直接转换", "INFO")
                if self._fix_moov_position(input_path, output_path):
                    success_count += 1
                    self._log(f"  - 结果: 转换成功", "SUCCESS")
                else:
                    fail_count += 1
                    self._log(f"  - 结果: 转换失败", "ERROR")
            else:
                # 正常流程：先检查是否需要处理
                needs_processing = self._check_needs_processing(input_path)
                
                if needs_processing:
                    # 需要处理，使用FFmpeg修复
                    self._log(f"  - 状态: 需要修复moov原子位置", "INFO")
                    if self._fix_moov_position(input_path, output_path):
                        success_count += 1
                        self._log(f"  - 结果: 修复成功", "SUCCESS")
                    else:
                        fail_count += 1
                        self._log(f"  - 结果: 修复失败", "ERROR")
                else:
                    # 不需要处理，直接复制到输出目录
                    self._log(f"  - 状态: 无需修复，直接复制", "INFO")
                    try:
                        shutil.copy2(input_path, output_path)
                        skipped_count += 1
                        self._log(f"  - 结果: 复制成功", "SUCCESS")
                    except Exception as e:
                        self._log(f"  - 结果: 复制失败 - {str(e)}", "ERROR")
                        fail_count += 1
            
            # 文件处理结束分隔符
            self._log("-" * 30)
            
        # 保存统计数据作为实例属性，以便UI可以访问
        self.success_count = success_count
        self.fail_count = fail_count
        self.skipped_count = skipped_count
        
        self._log(f"处理完成！成功修复: {success_count} 个文件, 直接复制: {skipped_count} 个文件, 失败: {fail_count} 个文件")
        self._log(f"处理后的文件保存在: {self.output_dir}")
        return True
    
    def _log(self, message, level="INFO"):
        """记录日志，同时更新UI（如果有）"""
        # 添加时间戳和日志级别
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 根据日志级别设置不同的前缀样式
        level_prefix = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "SUCCESS": "✅",
            "DEBUG": "🔧"
        }.get(level, "")
        
        formatted_message = f"[{timestamp}] {level_prefix} {message}"
        
        # 将所有日志（包括DEBUG）按时间顺序添加到统一的日志列表
        self.log_entries.append(formatted_message)
        
        # 对于DEBUG级别的日志，不打印到控制台和UI，只记录在日志列表中
        if level == "DEBUG":
            return
        
        # 打印到控制台
        print(formatted_message)
        
        # 如果有UI回调，更新UI
        if self.log_callback:
            self.log_callback(formatted_message)
    
    def cancel_processing(self):
        """取消正在进行的处理"""
        self.stop_flag = True

class MP4MoovFixerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"MP4 Moov原子前置工具 v{VERSION}")
        self.root.geometry("750x600")  # 进一步增大窗口尺寸
        self.root.minsize(700, 550)  # 调整最小窗口大小
        
        # 设置中文字体
        self.font = ('Microsoft YaHei UI', 10)
        self.bold_font = ('Microsoft YaHei UI', 10, 'bold')
        
        # 确保中文显示正常
        self.root.option_add("*Font", self.font)
        
        # 创建主框架，使用grid布局管理器
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 配置主框架的列和行权重，使其能够随窗口调整
        self.main_frame.grid_columnconfigure(0, weight=1)
        for i in range(5):
            self.main_frame.grid_rowconfigure(i, weight=1 if i == 2 else 0)  # 调整行权重分配
            
        # 初始化跳过检测的变量，默认设为True
        self.skip_detection = tk.BooleanVar(value=True)
        
        # 创建输入目录选择
        self.create_input_section()
        
        # 创建输出目录设置
        self.create_output_section()
        
        # 创建日志区域
        self.create_log_section()
        
        # 创建进度条
        self.create_progress_section()
        
        # 创建按钮区域
        self.create_button_section()
        
        # 初始化变量
        self.input_dir = os.getcwd()
        self.output_dir_name = "processed_videos"
        self.update_input_dir_display()
        self.is_processing = False
        self.fixer = None
        self.log_entries = []  # 存储普通日志
        self.debug_log_entries = []  # 存储调试日志
    
    def create_input_section(self):
        section = ttk.LabelFrame(self.main_frame, text="输入目录", padding="5")
        section.grid(row=0, column=0, sticky="ew", pady=5)
        
        # 配置section的列权重
        section.grid_columnconfigure(0, weight=1)
        
        self.input_dir_var = tk.StringVar()
        input_entry = ttk.Entry(section, textvariable=self.input_dir_var, font=self.font)
        input_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=2)
        
        browse_btn = ttk.Button(section, text="浏览...", command=self.browse_input_dir, width=10)
        browse_btn.grid(row=0, column=1, padx=5, pady=2)
    
    def create_output_section(self):
        section = ttk.LabelFrame(self.main_frame, text="输出设置", padding="5")
        section.grid(row=1, column=0, sticky="ew", pady=5)
        
        # 配置section的列权重
        section.grid_columnconfigure(0, weight=1)
        
        # 输出目录名称
        self.output_dir_var = tk.StringVar(value="processed_videos")
        output_entry = ttk.Entry(section, textvariable=self.output_dir_var, font=self.font)
        output_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=2)
        
        # 跳过moov检测复选框
        detection_frame = ttk.Frame(section)
        detection_frame.grid(row=1, column=0, sticky="w", padx=5, pady=2)
        
        self.skip_detection_checkbox = ttk.Checkbutton(
            detection_frame,
            text="跳过moov检测，直接全部转换",
            variable=self.skip_detection,
            onvalue=True,
            offvalue=False,
            state=tk.DISABLED
        )
        self.skip_detection_checkbox.pack(side=tk.LEFT)
    
    def create_log_section(self):
        section = ttk.LabelFrame(self.main_frame, text="处理日志", padding="5")
        section.grid(row=2, column=0, sticky="nsew", pady=5)
        
        # 配置section的列和行权重
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(0, weight=1)
        
        # 设置日志框的高度，防止其占据过多空间
        self.log_text = scrolledtext.ScrolledText(section, wrap=tk.WORD, font=self.font, height=15)
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.log_text.config(state=tk.DISABLED)
    
    def create_progress_section(self):
        section = ttk.Frame(self.main_frame)
        section.grid(row=3, column=0, sticky="ew", pady=5)
        
        # 配置section的列权重
        section.grid_columnconfigure(0, weight=1)
        
        # 当前处理文件标签
        self.progress_label = ttk.Label(section, text="准备就绪", font=self.font)
        self.progress_label.grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=2)
        
        # 进度条放在第二行
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(section, variable=self.progress_var, length=100, mode='determinate')
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=5, pady=2)
    
    def create_button_section(self):
        # 添加分隔符
        separator = ttk.Separator(self.main_frame, orient='horizontal')
        separator.grid(row=4, column=0, sticky="ew", pady=5)
        
        section = ttk.Frame(self.main_frame, padding="5")
        section.grid(row=5, column=0, sticky="ew", pady=5)
        
        # 使用一行布局，按钮均匀分布
        # 配置section的列权重
        section.grid_columnconfigure(0, weight=1)  # 左边距
        for i in range(1, 5):  # 按钮列
            section.grid_columnconfigure(i, weight=0)
        section.grid_columnconfigure(5, weight=1)  # 右边距
        
        # 所有按钮放在一行，统一宽度为12
        button_width = 12
        
        self.start_btn = ttk.Button(section, text="开始处理", command=self.start_processing, width=button_width)
        self.start_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.cancel_btn = ttk.Button(section, text="取消", command=self.cancel_processing, width=button_width, state=tk.DISABLED)
        self.cancel_btn.grid(row=0, column=2, padx=5, pady=5)
        
        self.export_log_btn = ttk.Button(section, text="导出日志", command=self.export_log, width=button_width)
        self.export_log_btn.grid(row=0, column=3, padx=5, pady=5)
        
        self.open_output_btn = ttk.Button(section, text="打开输出文件夹", command=self.open_output_folder, width=button_width)
        self.open_output_btn.grid(row=0, column=4, padx=5, pady=5)
    
    def browse_input_dir(self):
        directory = filedialog.askdirectory(title="选择MP4文件所在目录", initialdir=self.input_dir)
        if directory:
            self.input_dir = directory
            self.update_input_dir_display()
    
    def update_input_dir_display(self):
        self.input_dir_var.set(self.input_dir)
    
    def log(self, message):
        """更新UI日志显示"""
        self.log_text.config(state=tk.NORMAL)
        
        # 根据日志级别设置不同的文本颜色
        tag = None
        if "❌" in message:  # 错误
            tag = "error"
            self.log_text.tag_configure("error", foreground="red")
        elif "⚠️" in message:  # 警告
            tag = "warning"
            self.log_text.tag_configure("warning", foreground="orange")
        elif "✅" in message:  # 成功
            tag = "success"
            self.log_text.tag_configure("success", foreground="green")
        
        # 插入文本并应用标签
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # 保存日志到内存中，用于导出
        if not hasattr(self, 'log_entries'):
            self.log_entries = []
        self.log_entries.append(message)
    
    def export_log(self):
        """导出日志到文件（包含debug日志）"""
        # 合并所有日志（包括self和self.fixer中的）
        all_logs = []
        
        # 1. 添加self.log_entries（已经包含所有级别的日志）
        # if hasattr(self, 'log_entries'):
        #     all_logs.extend(self.log_entries or [])
        
        # 2. 添加self.fixer.log_entries（如果有）
        if hasattr(self, 'fixer') and self.fixer and hasattr(self.fixer, 'log_entries'):
            all_logs.extend(self.fixer.log_entries or [])
        
        if not all_logs:
            messagebox.showinfo("提示", "没有可导出的日志")
            return
            
        # 选择保存位置
        file_path = filedialog.asksaveasfilename(
            title="保存日志文件",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialdir=self.input_dir
        )
        
        if not file_path:
            return  # 用户取消了保存
            
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # 写入所有按时间顺序排序的日志
                f.write("\n".join(all_logs))
                      
            messagebox.showinfo("成功", f"日志已保存到: {file_path}\n\n(包含普通日志和调试信息)")
        except Exception as e:
            messagebox.showerror("错误", f"保存日志失败: {str(e)}")

    
    def update_progress(self, value, status=None):
        self.progress_var.set(value)
        if status:
            self.progress_label.config(text=status)
    
    def start_processing(self):
        if self.is_processing:
            return
        
        self.is_processing = True
        self.start_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        
        # 清空日志
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        
        # 获取输入参数
        self.input_dir = self.input_dir_var.get()
        self.output_dir_name = self.output_dir_var.get()
        
        # 在新线程中处理文件
        self.process_thread = threading.Thread(target=self.process_files_thread)
        self.process_thread.daemon = True
        self.process_thread.start()
    
    def process_files_thread(self):
        try:
            # 初始化修复器
            self.fixer = MP4MoovFixer(
                input_dir=self.input_dir,
                output_dir=self.output_dir_name,
                log_callback=self.log,
                progress_callback=self.update_progress,
                skip_detection=self.skip_detection.get()
            )
            
            # 处理文件
            success = self.fixer.process_files()
            
            # 更新UI状态
            self.root.after(0, self.processing_complete, success)
        except Exception as e:
            self.log(f"处理过程中发生错误: {str(e)}")
            self.root.after(0, self.processing_complete, False)
    
    def processing_complete(self, success):
        self.is_processing = False
        self.start_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        
        if success:
            self.update_progress(100, "处理完成")
            # 获取处理统计信息
            success_count = 0
            fail_count = 0
            skipped_count = 0
            if hasattr(self.fixer, 'success_count'):
                success_count = self.fixer.success_count
            if hasattr(self.fixer, 'fail_count'):
                fail_count = self.fixer.fail_count
            if hasattr(self.fixer, 'skipped_count'):
                skipped_count = self.fixer.skipped_count
                
            message = f"处理完成！\n\n成功修复: {success_count} 个文件\n直接复制: {skipped_count} 个文件\n失败: {fail_count} 个文件"
            
            # 如果有失败的文件，添加提示信息
            if fail_count > 0:
                message += "\n\n注意：有些文件处理失败，请查看日志了解详情。"
                
            messagebox.showinfo("处理结果", message)
        else:
            self.update_progress(0, "处理失败")
            messagebox.showerror("处理失败", "处理过程中发生错误，请查看日志了解详情。")
    
    def cancel_processing(self):
        if messagebox.askyesno("确认取消", "确定要取消处理吗？"):
            if self.fixer:
                self.fixer.cancel_processing()
            self.is_processing = False
            self.start_btn.config(state=tk.NORMAL)
            self.cancel_btn.config(state=tk.DISABLED)
            self.update_progress(0, "已取消")
            self.log("处理已取消")
    
    def open_output_folder(self):
        output_path = os.path.join(self.input_dir, self.output_dir_name)
        if os.path.exists(output_path):
            # 打开文件资源管理器
            if sys.platform == 'win32':
                os.startfile(output_path)
            elif sys.platform == 'darwin':
                # 添加creationflags参数以避免在macOS上弹出黑框
                kwargs = {}
                result = subprocess.run(['open', output_path], **kwargs)
            else:
                # 添加creationflags参数以避免在Linux上弹出黑框
                kwargs = {}
                result = subprocess.run(['xdg-open', output_path], **kwargs)
        else:
            messagebox.showwarning("警告", "输出文件夹不存在")

def main():
    # 检查参数，如果有命令行参数则使用命令行模式
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description=f'自动修复MP4文件的moov原子位置 (v{VERSION})')
        parser.add_argument('--version', action='version', version=f'%(prog)s {VERSION}')
        parser.add_argument('-i', '--input', help='输入目录路径，默认为当前目录')
        parser.add_argument('-o', '--output', help='输出目录名称，默认为"processed_videos"')
        parser.add_argument('-s', '--skip-detection', action='store_true', help='跳过moov检测，直接全部转换')
        args = parser.parse_args()
        
        fixer = MP4MoovFixer(
            input_dir=args.input,
            output_dir=args.output if args.output else "processed_videos",
            skip_detection=args.skip_detection
        )
        fixer.process_files()
    else:
        # 否则使用GUI模式
        root = tk.Tk()
        app = MP4MoovFixerApp(root)
        root.mainloop()

if __name__ == "__main__":
    main()