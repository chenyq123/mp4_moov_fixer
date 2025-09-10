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

class MP4MoovFixer:
    def __init__(self, input_dir=None, output_dir="processed_videos", log_callback=None, progress_callback=None):
        self.input_dir = input_dir if input_dir else os.getcwd()
        self.output_dir = os.path.join(self.input_dir, output_dir)
        self.ffmpeg_path = self._get_ffmpeg_path()
        self.log_callback = log_callback  # 用于UI日志更新的回调函数
        self.progress_callback = progress_callback  # 用于UI进度条更新的回调函数
        self.stop_flag = False  # 用于取消处理的标志
    
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
    
    def _is_moov_at_end(self, mp4_file):
        """检查MP4文件的moov原子是否在文件末尾"""
        try:
            # 使用ffprobe检查视频信息
            cmd = [self.ffmpeg_path, "-v", "error", "-show_entries", "format=is_avc", 
                   "-of", "default=noprint_wrappers=1:nokey=1", mp4_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # 更可靠的方法是检查文件结构
            cmd = [self.ffmpeg_path, "-i", mp4_file, "-c", "copy", "-movflags", "+faststart", 
                   "-f", "mp4", "-y", "NUL" if sys.platform == "win32" else "/dev/null"]
            subprocess.run(cmd, capture_output=True)
            
            # 实际上，我们可以直接使用ffmpeg的faststart选项重新编码，不需要预先检查
            return True
        except Exception:
            return True  # 默认假设需要处理
    
    def _fix_moov_position(self, input_file, output_file):
        """使用FFmpeg将moov原子移到文件开头"""
        try:
            cmd = [self.ffmpeg_path, "-i", input_file, "-c", "copy", "-movflags", 
                   "+faststart", "-y", output_file]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except Exception as e:
            self._log(f"处理文件失败 {input_file}: {e}")
            return False
    
    def process_files(self):
        """处理所有MP4文件"""
        # 检查并下载FFmpeg
        if not self.ffmpeg_path:
            if not self._download_ffmpeg():
                self._log("无法获取FFmpeg，程序退出")
                return False
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 获取所有MP4文件
        mp4_files = [f for f in os.listdir(self.input_dir) if f.lower().endswith('.mp4')]
        
        if not mp4_files:
            self._log("没有找到MP4文件")
            return True
        
        self._log(f"找到 {len(mp4_files)} 个MP4文件，开始处理...")
        
        # 处理每个文件
        success_count = 0
        fail_count = 0
        
        for i, mp4_file in enumerate(mp4_files):
            if self.stop_flag:
                self._log("处理已取消")
                return False
            
            input_path = os.path.join(self.input_dir, mp4_file)
            output_path = os.path.join(self.output_dir, mp4_file)
            
            # 更新进度
            progress_percent = (i + 1) / len(mp4_files) * 100
            if self.progress_callback:
                self.progress_callback(progress_percent, f"处理中: {mp4_file}")
            
            # 处理文件
            if self._fix_moov_position(input_path, output_path):
                success_count += 1
                self._log(f"已处理: {mp4_file}")
            else:
                fail_count += 1
            
        self._log(f"处理完成！成功: {success_count} 个文件, 失败: {fail_count} 个文件")
        self._log(f"处理后的文件保存在: {self.output_dir}")
        return True
    
    def _log(self, message):
        """记录日志，同时更新UI（如果有）"""
        print(message)
        if self.log_callback:
            self.log_callback(message)
    
    def cancel_processing(self):
        """取消正在进行的处理"""
        self.stop_flag = True

class MP4MoovFixerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MP4 Moov原子前置工具")
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
            self.main_frame.grid_rowconfigure(i, weight=1 if i == 2 else 0)
        
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
        section = ttk.LabelFrame(self.main_frame, text="输出目录名称", padding="5")
        section.grid(row=1, column=0, sticky="ew", pady=5)
        
        # 配置section的列权重
        section.grid_columnconfigure(0, weight=1)
        
        self.output_dir_var = tk.StringVar(value="processed_videos")
        output_entry = ttk.Entry(section, textvariable=self.output_dir_var, font=self.font)
        output_entry.grid(row=0, column=0, sticky="ew", padx=5, pady=2)
    
    def create_log_section(self):
        section = ttk.LabelFrame(self.main_frame, text="处理日志", padding="5")
        section.grid(row=2, column=0, sticky="nsew", pady=5)
        
        # 配置section的列和行权重
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(section, wrap=tk.WORD, font=self.font)
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.log_text.config(state=tk.DISABLED)
    
    def create_progress_section(self):
        section = ttk.Frame(self.main_frame)
        section.grid(row=3, column=0, sticky="ew", pady=5)
        
        # 配置section的列权重
        section.grid_columnconfigure(0, weight=1)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(section, variable=self.progress_var, length=100, mode='determinate')
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=5, pady=2)
        
        self.progress_label = ttk.Label(section, text="准备就绪", font=self.font)
        self.progress_label.grid(row=0, column=1, padx=5, pady=2)
    
    def create_button_section(self):
        # 添加分隔符
        separator = ttk.Separator(self.main_frame, orient='horizontal')
        separator.grid(row=4, column=0, sticky="ew", pady=5)
        
        section = ttk.Frame(self.main_frame, padding="5")
        section.grid(row=5, column=0, sticky="ew", pady=5)
        
        # 配置section的列权重，确保按钮居中
        section.grid_columnconfigure(0, weight=1)
        section.grid_columnconfigure(1, weight=0)
        section.grid_columnconfigure(2, weight=0)
        section.grid_columnconfigure(3, weight=1)
        
        # 左侧按钮
        self.start_btn = ttk.Button(section, text="开始处理", command=self.start_processing, width=15)
        self.start_btn.grid(row=0, column=1, padx=5, pady=5)
        
        self.cancel_btn = ttk.Button(section, text="取消", command=self.cancel_processing, width=15, state=tk.DISABLED)
        self.cancel_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # 右侧按钮
        self.open_output_btn = ttk.Button(section, text="打开输出文件夹", command=self.open_output_folder, width=15)
        self.open_output_btn.grid(row=0, column=4, padx=5, pady=5)
        
        # 额外配置列权重以确保按钮位置正确
        section.grid_columnconfigure(4, weight=0)
    
    def browse_input_dir(self):
        directory = filedialog.askdirectory(title="选择MP4文件所在目录", initialdir=self.input_dir)
        if directory:
            self.input_dir = directory
            self.update_input_dir_display()
    
    def update_input_dir_display(self):
        self.input_dir_var.set(self.input_dir)
    
    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
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
                progress_callback=self.update_progress
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
            messagebox.showinfo("成功", "所有文件处理完成！")
        else:
            self.update_progress(0, "处理失败")
    
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
                subprocess.run(['open', output_path])
            else:
                subprocess.run(['xdg-open', output_path])
        else:
            messagebox.showwarning("警告", "输出文件夹不存在")

def main():
    # 检查参数，如果有命令行参数则使用命令行模式
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description='自动修复MP4文件的moov原子位置')
        parser.add_argument('-i', '--input', help='输入目录路径，默认为当前目录')
        parser.add_argument('-o', '--output', help='输出目录名称，默认为"processed_videos"')
        args = parser.parse_args()
        
        fixer = MP4MoovFixer(
            input_dir=args.input,
            output_dir=args.output if args.output else "processed_videos"
        )
        fixer.process_files()
    else:
        # 否则使用GUI模式
        root = tk.Tk()
        app = MP4MoovFixerApp(root)
        root.mainloop()

if __name__ == "__main__":
    main()