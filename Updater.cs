using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

// Runs from the update cache, outside the runtime that it replaces.
class Updater {
    static JavaScriptSerializer json=new JavaScriptSerializer { MaxJsonLength=8*1024*1024 };
    static string Full(string path) { return Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar); }
    static bool Within(string root,string path) {
        return Full(path).StartsWith(Full(root)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase);
    }
    static void NoLinks(string path) {
        string current=Full(path);
        while(!String.IsNullOrEmpty(current)) {
            if((File.Exists(current)||Directory.Exists(current)) && (File.GetAttributes(current)&FileAttributes.ReparsePoint)!=0)
                throw new Exception("Ссылки и junction в пути обновления не поддерживаются: "+current);
            current=Path.GetDirectoryName(current);
        }
    }
    static string Member(string root,string name) {
        if(String.IsNullOrEmpty(name)||name.Contains("\\")||name.Contains(":")||Path.IsPathRooted(name))throw new Exception("Некорректный путь");
        string[] parts=name.Split('/');
        if(parts[0].Equals("data",StringComparison.OrdinalIgnoreCase)||parts[0].Equals("backups",StringComparison.OrdinalIgnoreCase))throw new Exception("Обновление не может заменять данные");
        foreach(string part in parts)
            if(part.Length==0||part=="."||part==".."||part.EndsWith(".")||part.EndsWith(" "))throw new Exception("Некорректный путь");
        string result=Full(Path.Combine(root,name.Replace('/',Path.DirectorySeparatorChar)));
        if(!Within(root,result))throw new Exception("Путь за пределами приложения");
        NoLinks(result);return result;
    }
    static string Hash(string file) {
        using(var input=File.OpenRead(file))using(var sha=SHA256.Create())return BitConverter.ToString(sha.ComputeHash(input)).Replace("-","").ToLowerInvariant();
    }
    static void Copy(string source,string target) {
        Directory.CreateDirectory(Path.GetDirectoryName(target));
        Exception last=null;
        for(int attempt=0;attempt<30;attempt++) {
            string temp=target+".update-"+Guid.NewGuid().ToString("N");
            try {
                File.Copy(source,temp,false);
                if(File.Exists(target))File.Replace(temp,target,null);else File.Move(temp,target);
                return;
            } catch(IOException error) { last=error;Thread.Sleep(100); }
            finally { if(File.Exists(temp))File.Delete(temp); }
        }
        throw last;
    }
    static void Status(string path,object result) {
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        string temp=path+".tmp-"+Guid.NewGuid().ToString("N");
        File.WriteAllText(temp,json.Serialize(result),new UTF8Encoding(false));
        if(File.Exists(path))File.Replace(temp,path,null);else File.Move(temp,path);
    }
    [STAThread] static int Main(string[] args) {
        string target=null,stage=null,backup=null,status=null,version="";
        bool quiet=false,restart=false,started=false;
        var changed=new List<string>();var existed=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var retired=new List<string>();
        try {
            if(args.Length!=1)throw new Exception("Не указан план обновления");
            var plan=json.Deserialize<Dictionary<string,object>>(File.ReadAllText(args[0],Encoding.UTF8));
            target=Full((string)plan["target"]);stage=Full((string)plan["stage"]);
            quiet=Convert.ToBoolean(plan["quiet"]);restart=Convert.ToBoolean(plan["restart"]);version=(string)plan["version"];
            NoLinks(target);NoLinks(stage);
            if(target.Equals(stage,StringComparison.OrdinalIgnoreCase)||Within(target,stage)||Within(stage,target))throw new Exception("Каталоги обновления должны быть независимыми");
            if(!File.Exists(Path.Combine(target,"AFTERPLAY.exe"))||!File.Exists(Path.Combine(target,"SHA256SUMS.json")))throw new Exception("Это не портативная установка AFTERPLAY");
            status=Full((string)plan["status"]);
            // Standard installations and explicitly selected external data folders
            // both use the application's update-status.json file.
            if(Path.GetFileName(status)!="update-status.json")throw new Exception("Некорректный журнал обновления");
            NoLinks(status);
            // Only retire obsolete program files catalogued by the old bundle,
            // and only if their bytes still match that catalog. User-created or
            // locally modified files are preserved. Every retirement is backed up.
            Dictionary<string,string> previous=null;
            try { previous=json.Deserialize<Dictionary<string,string>>(File.ReadAllText(Path.Combine(target,"SHA256SUMS.json"))); }
            catch(ArgumentException) { }
            var files=new List<Dictionary<string,object>>();var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach(object item in (IEnumerable)plan["files"]) {
                var file=(Dictionary<string,object>)item;string name=(string)file["path"];
                string source=Member(stage,name);Member(target,name);
                if(!names.Add(name))throw new Exception("Повторяющийся файл");
                if(!Hash(source).Equals((string)file["sha256"],StringComparison.Ordinal))throw new Exception("Повреждён файл обновления: "+name);
                files.Add(file);
            }
            foreach(string name in new [] {"app.py","version.py","AFTERPLAY.exe","Updater.exe","SHA256SUMS.json","runtime/pythonw.exe"})
                if(!names.Contains(name))throw new Exception("Неполный комплект: "+name);
            if(previous!=null)foreach(var item in previous) {
                if(names.Contains(item.Key))continue;
                string old=Member(target,item.Key);
                if(File.Exists(old)&&Hash(old).Equals(item.Value,StringComparison.OrdinalIgnoreCase))retired.Add(item.Key);
            }
            int parent=Convert.ToInt32(plan["parent_pid"]);
            if(parent>0) {
                Process process=null;
                try { process=Process.GetProcessById(parent); } catch(ArgumentException) { }
                if(process!=null)using(process) { if(!process.WaitForExit(120000))throw new Exception("AFTERPLAY не закрылся. Повторите обновление."); }
            }
            backup=Path.Combine(target,"backups","update-"+DateTime.Now.ToString("yyyyMMdd-HHmmss")+"-"+Guid.NewGuid().ToString("N").Substring(0,8));
            NoLinks(backup);Directory.CreateDirectory(backup);
            // Finish the complete backup before replacing the first file.
            foreach(var file in files) {
                string name=(string)file["path"],old=Member(target,name);
                if(File.Exists(old)) { Copy(old,Member(backup,name));existed.Add(name); }
            }
            foreach(string name in retired) { Copy(Member(target,name),Member(backup,name));existed.Add(name); }
            started=true;
            foreach(var file in files) {
                string name=(string)file["path"];
                Copy(Member(stage,name),Member(target,name));changed.Add(name);
            }
            foreach(string name in retired) { File.Delete(Member(target,name));changed.Add(name); }
            Status(status,new { success=true,version=version,backup=backup,stage=stage,retired=retired,message="Обновление установлено. Записи и настройки сохранены." });
            if(restart)Process.Start(new ProcessStartInfo(Path.Combine(target,"AFTERPLAY.exe")) { WorkingDirectory=target,UseShellExecute=false });
            return 0;
        } catch(Exception error) {
            string rollbackError="";
            if(started)for(int i=changed.Count-1;i>=0;i--) {
                try {
                    string name=changed[i],path=Member(target,name);
                    if(existed.Contains(name))Copy(Member(backup,name),path);
                    else if(File.Exists(path))File.Delete(path);
                } catch(Exception restore) { rollbackError+="\n"+restore.Message; }
            }
            string message="Не удалось установить обновление: "+error.Message;
            if(started)message+=rollbackError.Length==0?"\nПредыдущие файлы восстановлены.":"\nОшибка восстановления: "+rollbackError;
            if(backup!=null)message+="\nРезервная копия: "+backup;
            try { if(status!=null)Status(status,new { success=false,version=version,backup=backup,message=message }); } catch { }
            if(!quiet)MessageBox.Show(message,"AFTERPLAY — обновление",MessageBoxButtons.OK,MessageBoxIcon.Error);
            return 1;
        }
    }
}
