using System;
using System.Diagnostics;
using System.Media;
using System.Threading;
using AfterplayAudio;

class ProcessAudioProbe {
 [STAThread] static int Main(string[] args) {
  if(args.Length==0) {
   var unused=new ProcessCapture();unused.Dispose();unused.Dispose();
   try { unused.Start(1,false);return 2; }
   catch(ObjectDisposedException) { Console.WriteLine("Unused capture disposal OK");return 0; }
  }
  using(var player=new SoundPlayer(args[0])) {
   player.Load();player.PlayLooping();Thread.Sleep(200);
   foreach(ApartmentState apartment in new[]{ApartmentState.STA,ApartmentState.MTA}) {
    foreach(bool foreign in new[]{false,true}) {
     Exception error=null;
     var caller=new Thread(()=> {
      try {
       for(int cycle=0;cycle<3;cycle++) {
        using(var capture=new ProcessCapture()) {
         capture.Start((uint)Process.GetCurrentProcess().Id,false);
         long bytes=0;ulong last=0;var watch=Stopwatch.StartNew();
         while(watch.ElapsedMilliseconds<200) {
          var packet=capture.ReadPacket();
          if(packet==null) { Thread.Sleep(5);continue; }
          if(packet.Data.Length%8!=0 || packet.Qpc100ns<last)throw new Exception("Invalid PCM timeline");
          last=packet.Qpc100ns;bytes+=packet.Data.Length;
         }
         if(bytes==0)throw new Exception("No loopback PCM received");
         if(foreign) {
          Exception stopError=null;
          var closer=new Thread(()=>{try {capture.Dispose();}catch(Exception e){stopError=e;}});
          closer.SetApartmentState(ApartmentState.STA);closer.Start();
          if(!closer.Join(5000))throw new Exception("Dispose did not finish");
          if(stopError!=null)throw stopError;
         } else capture.Dispose();
         capture.Dispose();
         if(!String.IsNullOrEmpty(capture.Error))throw new Exception(capture.Error);
         Console.WriteLine("OK "+apartment+" foreign="+foreign+" cycle="+cycle+" PCM="+bytes);
        }
       }
      }catch(Exception e){error=e;}
     });
     caller.SetApartmentState(apartment);caller.Start();
     if(!caller.Join(25000)){Console.WriteLine("Caller timed out");return 3;}
     if(error!=null){Console.WriteLine(error);return 2;}
    }
   }
  }
  return 0;
 }
}
