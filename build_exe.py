import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path
import time
import uuid

class AppPackager:
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.main_script = os.path.join(self.script_dir, "mp4_moov_fixer.py")
        self.dist_dir = os.path.join(self.script_dir, "dist")
        self.build_dir = os.path.join(self.script_dir, "build")
        self.spec_dir = self.script_dir
        self.app_name = "MP4MoovFixer"
        self.os = platform.system()
    
    def prepare_build_environment(self):
        """准备打包环境"""
        print("准备打包环境...")
        
        # 检查dist目录是否存在
        print(f"使用现有dist目录: {self.dist_dir}")
        os.makedirs(self.dist_dir, exist_ok=True)
        
        # 检查主脚本是否存在
        if not os.path.exists(self.main_script):
            print(f"错误: 找不到主脚本 {self.main_script}")
            return False
        
        # 检查pyinstaller是否已安装
        if shutil.which("pyinstaller") is None:
            print("pyinstaller未安装，尝试安装...")
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller>=5.0.0"], check=True)
            except subprocess.CalledProcessError:
                print("pyinstaller安装失败，请手动安装: pip install pyinstaller")
                return False
        
        # macOS特定依赖 - 用于创建DMG
        if self.os == "Darwin":
            if shutil.which("create-dmg") is None:
                print("create-dmg未安装，尝试使用hdiutil创建DMG...")
                # 不强制安装create-dmg，使用系统自带的hdiutil作为备选
        
        return True
    
    def build_windows_exe(self):
        """在Windows上打包为exe"""
        print("开始打包Windows可执行文件...")
        
        # 处理可能存在的锁定文件
        exe_name = self.app_name
        existing_exe = os.path.join(self.dist_dir, f"{exe_name}.exe")
        use_temp_name = False
        temp_exe_name = None
        
        # 检查并处理已存在的exe文件
        if os.path.exists(existing_exe):
            try:
                # 生成唯一的临时文件名
                temp_name = f"{exe_name}_old_{uuid.uuid4().hex[:8]}.exe"
                temp_exe = os.path.join(self.dist_dir, temp_name)
                os.rename(existing_exe, temp_exe)
                print(f"已重命名锁定的文件为: {temp_name}")
            except Exception as e:
                print(f"无法重命名锁定的文件: {e}")
                # 使用临时文件名打包
                print("将使用临时文件名打包...")
                timestamp = int(time.time())
                temp_exe_name = f"{exe_name}_{timestamp}"
                exe_name = temp_exe_name
                use_temp_name = True
        
        # 构建pyinstaller命令参数
        cmd = [
            "pyinstaller",
            "--name", exe_name,  # 输出的可执行文件名
            "--onefile",  # 打包成单个文件
            "--windowed",  # 窗口模式，不显示控制台
            "--add-data", f"{os.path.join(self.script_dir, 'requirements.txt')};.",  # 添加依赖文件
            "--distpath", self.dist_dir,
            "--workpath", self.build_dir,
            "--specpath", self.spec_dir,
            # 确保中文显示正常
            "--hidden-import", "tkinter",
            "--hidden-import", "tkinter.filedialog",
            "--hidden-import", "tkinter.ttk",
            "--hidden-import", "tkinter.scrolledtext",
            "--hidden-import", "tkinter.messagebox",
            "--hidden-import", "tqdm",
            "--hidden-import", "requests",
            # 添加图标（如果有的话）
            # "--icon", "icon.ico",
            self.main_script
        ]
        
        try:
            # 运行pyinstaller命令
            subprocess.run(cmd, check=True)
            print(f"打包成功！可执行文件位于: {self.dist_dir}")
            
            # 如果使用了临时名称打包，尝试将其重命名回原来的名称
            if use_temp_name and temp_exe_name:
                temp_result_exe = os.path.join(self.dist_dir, f"{temp_exe_name}.exe")
                if os.path.exists(temp_result_exe):
                    try:
                        os.rename(temp_result_exe, existing_exe)
                        print(f"已将临时文件 {temp_exe_name}.exe 重命名为 {self.app_name}.exe")
                    except Exception as e:
                        print(f"无法重命名临时文件: {e}")
                        print(f"请手动将 {temp_exe_name}.exe 重命名为 {self.app_name}.exe")
                
            return True
        except subprocess.CalledProcessError as e:
            print(f"打包失败: {e}")
            return False
    
    def build_macos_app(self):
        """在macOS上打包为.app应用"""
        print("开始打包macOS应用...")
        
        # 构建pyinstaller命令参数 - macOS版本
        cmd = [
            "pyinstaller",
            "--name", self.app_name,
            "--onefile",
            "--windowed",
            "--add-data", f"{os.path.join(self.script_dir, 'requirements.txt')}:.",  # macOS使用冒号分隔
            "--distpath", self.dist_dir,
            "--workpath", self.build_dir,
            "--specpath", self.spec_dir,
            # 确保中文显示正常
            "--hidden-import", "tkinter",
            "--hidden-import", "tkinter.filedialog",
            "--hidden-import", "tkinter.ttk",
            "--hidden-import", "tkinter.scrolledtext",
            "--hidden-import", "tkinter.messagebox",
            "--hidden-import", "tqdm",
            "--hidden-import", "requests",
            # 添加图标（如果有的话）
            # "--icon", "icon.icns",
            self.main_script
        ]
        
        try:
            # 运行pyinstaller命令
            subprocess.run(cmd, check=True)
            print(f"macOS应用打包成功！可执行文件位于: {self.dist_dir}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"macOS应用打包失败: {e}")
            return False
    
    def create_macos_dmg(self):
        """在macOS上创建DMG安装包"""
        print("开始创建macOS DMG安装包...")
        
        # 检查.app文件是否存在
        app_bundle = os.path.join(self.dist_dir, f"{self.app_name}.app")
        if not os.path.exists(app_bundle):
            print(f"错误: 找不到应用包 {app_bundle}")
            return False
        
        # 定义DMG输出路径
        dmg_path = os.path.join(self.dist_dir, f"{self.app_name}.dmg")
        
        # 清理已存在的DMG文件
        if os.path.exists(dmg_path):
            try:
                os.remove(dmg_path)
                print(f"已删除旧的DMG文件: {dmg_path}")
            except Exception as e:
                print(f"无法删除旧的DMG文件: {e}")
                # 使用临时名称继续
                timestamp = int(time.time())
                dmg_path = os.path.join(self.dist_dir, f"{self.app_name}_{timestamp}.dmg")
        
        try:
            # 方法1：使用create-dmg工具（如果可用）
            if shutil.which("create-dmg"):
                cmd = [
                    "create-dmg",
                    "--volname", self.app_name,
                    "--window-pos", "200", "120",
                    "--window-size", "800", "400",
                    "--icon-size", "100",
                    "--icon", f"{self.app_name}.app", "200", "190",
                    "--hide-extension", f"{self.app_name}.app",
                    "--app-drop-link", "600", "185",
                    dmg_path,
                    self.dist_dir
                ]
                subprocess.run(cmd, check=True)
            else:
                # 方法2：使用系统自带的hdiutil
                # 创建临时磁盘镜像
                temp_dir = os.path.join(self.script_dir, "temp_dmg")
                os.makedirs(temp_dir, exist_ok=True)
                
                # 复制应用到临时目录
                shutil.copytree(app_bundle, os.path.join(temp_dir, f"{self.app_name}.app"))
                
                # 复制README到临时目录
                readme_path = os.path.join(self.script_dir, "README.md")
                if os.path.exists(readme_path):
                    shutil.copy2(readme_path, os.path.join(temp_dir, "README.md"))
                
                # 创建DMG
                cmd = [
                    "hdiutil", "create",
                    "-fs", "HFS+",
                    "-volname", self.app_name,
                    "-srcfolder", temp_dir,
                    dmg_path
                ]
                subprocess.run(cmd, check=True)
                
                # 清理临时目录
                shutil.rmtree(temp_dir)
            
            print(f"DMG创建成功: {dmg_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"DMG创建失败: {e}")
            return False
    
    def copy_readme(self):
        """复制README.md到dist目录"""
        readme_path = os.path.join(self.script_dir, "README.md")
        if os.path.exists(readme_path):
            try:
                # 使用文件读写方式避免文件锁定问题
                with open(readme_path, 'r', encoding='utf-8') as src:
                    with open(os.path.join(self.dist_dir, "README.md"), 'w', encoding='utf-8') as dst:
                        dst.write(src.read())
                print("已复制README.md到dist目录")
            except Exception as e:
                print(f"复制README.md时出错: {e}")
    
    def run(self):
        """运行完整的打包流程"""
        print(f"=== {self.app_name} 打包脚本 ===")
        print(f"当前操作系统: {self.os}")
        
        # 准备环境
        if not self.prepare_build_environment():
            return False
        
        # 根据操作系统执行不同的打包流程
        if self.os == "Windows":
            success = self.build_windows_exe()
        elif self.os == "Darwin":
            # macOS: 先打包成.app，再创建DMG
            success = self.build_macos_app()
            if success:
                # 复制README
                self.copy_readme()
                # 询问是否创建DMG
                print("\n是否要创建DMG安装包？")
                create_dmg = input("输入 'y' 创建DMG，其他键跳过: ").lower() == 'y'
                if create_dmg:
                    dmg_success = self.create_macos_dmg()
                    if not dmg_success:
                        print("DMG创建失败，但应用程序已成功打包")
        else:
            print(f"当前操作系统 {self.os} 暂不支持一键打包")
            print("您可以尝试手动打包: pyinstaller --name {self.app_name} --onefile --windowed {self.main_script}")
            return False
        
        # 在Windows和非DMG的macOS上也复制README
        if (self.os == "Windows" or (self.os == "Darwin" and not create_dmg)):
            self.copy_readme()
        
        return success

if __name__ == "__main__":
    packager = AppPackager()
    if packager.run():
        print("\n打包完成！您可以在dist目录中找到生成的可执行文件。")
    else:
        print("\n打包失败，请查看错误信息并尝试解决问题。")

    # 让窗口保持打开状态，直到用户按下任意键
    input("按任意键退出...")