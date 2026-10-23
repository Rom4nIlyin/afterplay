using System;
using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Threading;

namespace GameClipsAudio {
 [ComVisible(true), Guid("41D949AB-9862-444A-80F6-C261334DA5EB"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
 public interface ICompletion { [PreserveSig] int ActivateCompleted(IAsyncOperation operation); }
 [ComImport, Guid("72A22D78-CDE4-431D-B8CC-843A71199B6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
 public interface IAsyncOperation { [PreserveSig] int GetActivateResult(out int result, [MarshalAs(UnmanagedType.IUnknown)] out object audio); }
 [ComVisible(true), Guid("94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
 public interface IAgile { }
 [ComImport, Guid("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
 interface IAudioClient {
  [PreserveSig] int Initialize(int mode, uint flags, long duration, long period, ref WaveFormat format, IntPtr session);
  [PreserveSig] int GetBufferSize(out uint frames);
  [PreserveSig] int GetStreamLatency(out long value);
  [PreserveSig] int GetCurrentPadding(out uint frames);
  [PreserveSig] int IsFormatSupported(int mode, IntPtr format, out IntPtr closest);
  [PreserveSig] int GetMixFormat(out IntPtr format);
  [PreserveSig] int GetDevicePeriod(out long normal, out long minimum);
  [PreserveSig] int Start();
  [PreserveSig] int Stop();
  [PreserveSig] int Reset();
  [PreserveSig] int SetEventHandle(IntPtr handle);
  [PreserveSig] int GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object service);
 }
 [ComImport, Guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
 interface ICapture {
  [PreserveSig] int GetBuffer(out IntPtr data, out uint frames, out uint flags, out ulong position, out ulong qpc);
  [PreserveSig] int ReleaseBuffer(uint frames);
  [PreserveSig] int GetNextPacketSize(out uint frames);
 }
 [StructLayout(LayoutKind.Sequential, Pack=2)]
 struct WaveFormat { public ushort tag, channels; public uint rate, average; public ushort align, bits, extra; }
 [StructLayout(LayoutKind.Explicit, Size=24)]
 struct PropVariant { [FieldOffset(0)] public ushort vt; [FieldOffset(8)] public uint size; [FieldOffset(16)] public IntPtr data; }
 [ComVisible(true), ClassInterface(ClassInterfaceType.None)]
 public class Completion : ICompletion, IAgile {
  internal ManualResetEvent done = new ManualResetEvent(false);
  internal object audio; internal int result;
  public int ActivateCompleted(IAsyncOperation operation) {
   try { int hr; object obj; int call=operation.GetActivateResult(out hr,out obj); result=call<0?call:hr; audio=obj; }
   catch(Exception e) { result=Marshal.GetHRForException(e); }
   finally { done.Set(); } return 0;
  }
 }
 public sealed class AudioPacket {
  public byte[] Data { get; set; }
  public ulong Qpc100ns { get; set; }
  public uint Flags { get; set; }
 }
 public sealed class ProcessCapture : IDisposable {
  [DllImport("Mmdevapi.dll", CharSet=CharSet.Unicode)]
  static extern int ActivateAudioInterfaceAsync(string path, ref Guid iid, ref PropVariant param, ICompletion completion, out IAsyncOperation operation);
  readonly ConcurrentQueue<AudioPacket> packets=new ConcurrentQueue<AudioPacket>();
  readonly AutoResetEvent signal=new AutoResetEvent(false);
  readonly ManualResetEvent stop=new ManualResetEvent(false);
  IAudioClient client; ICapture capture; Thread thread;
  bool disposed;
  public string Error { get; private set; }
  static void Check(int hr) { Marshal.ThrowExceptionForHR(hr); }
  public void Start(uint pid, bool exclude) {
   IntPtr blob=Marshal.AllocHGlobal(12);
   var completion=new Completion(); IAsyncOperation operation=null;
   try {
    Marshal.WriteInt32(blob,0,1); Marshal.WriteInt32(blob,4,unchecked((int)pid)); Marshal.WriteInt32(blob,8,exclude?1:0);
    var param=new PropVariant { vt=65,size=12,data=blob };
    Guid iid=new Guid("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2");
    Check(ActivateAudioInterfaceAsync("VAD\\Process_Loopback",ref iid,ref param,completion,out operation));
    // Keep the activation blob alive until the asynchronous operation completes.
    completion.done.WaitOne(); Check(completion.result);
    client=(IAudioClient)completion.audio;
    var format=new WaveFormat { tag=3,channels=2,rate=48000,average=384000,align=8,bits=32,extra=0 };
    Check(client.Initialize(0,0x88060000,0,0,ref format,IntPtr.Zero));
    Guid captureId=new Guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317"); object service;
    Check(client.GetService(ref captureId,out service)); capture=(ICapture)service;
    Check(client.SetEventHandle(signal.SafeWaitHandle.DangerousGetHandle())); Check(client.Start());
    thread=new Thread(Pump); thread.IsBackground=true; thread.Start();
   } catch { Dispose(); throw; }
   finally { Marshal.FreeHGlobal(blob); if(operation!=null)Marshal.ReleaseComObject(operation); GC.KeepAlive(completion); }
  }
  void Pump() {
   try {
    WaitHandle[] waits={stop,signal};
    while(WaitHandle.WaitAny(waits,100)!=0) {
     uint count; Check(capture.GetNextPacketSize(out count));
     while(count>0) {
      IntPtr data; uint frames,flags; ulong position,qpc;
      Check(capture.GetBuffer(out data,out frames,out flags,out position,out qpc));
      try {
       byte[] buffer=new byte[checked((int)frames*8)];
       if((flags&2)==0 && data!=IntPtr.Zero)Marshal.Copy(data,buffer,0,buffer.Length);
       packets.Enqueue(new AudioPacket { Data=buffer,Qpc100ns=qpc,Flags=flags });
       AudioPacket discarded; while(packets.Count>128)packets.TryDequeue(out discarded);
      } finally { Check(capture.ReleaseBuffer(frames)); }
      Check(capture.GetNextPacketSize(out count));
     }
    }
   } catch(Exception e) { Error=e.Message; }
  }
  public AudioPacket ReadPacket() { AudioPacket block; return packets.TryDequeue(out block)?block:null; }
  public byte[] Read() { AudioPacket block=ReadPacket();return block==null?null:block.Data; }
  public void Dispose() {
   if(disposed)return;disposed=true;
   stop.Set(); if(thread!=null)thread.Join(2000);
   if(client!=null) { client.Stop(); }
   if(capture!=null) { Marshal.ReleaseComObject(capture);capture=null; }
   if(client!=null) { Marshal.ReleaseComObject(client);client=null; }
   stop.Dispose();signal.Dispose();
  }
 }
}
