"""Aligned PCM sources; mix first for ordinary players, then isolated tracks."""
from fractions import Fraction
import queue
from capture_media import AudioTimeline

TITLES=('Общий звук','Игра','Discord / чат')


class AudioPackets:
    def __init__(self,mux,device,default_queue,epoch,offset_ms):
        self.rate=device['rate'];self.channels=device['channels'];self.cursor=0
        sources=device.get('sources') or [{'queue':default_queue}]
        self.queues=[source['queue'] for source in sources]
        self.timelines=[AudioTimeline(self.rate,self.channels,epoch,offset_ms) for _ in sources]
        self.multitrack=len(sources)>1
        self.streams=[]
        titles=device.get('titles') or (TITLES if self.multitrack else TITLES[:1])
        for title in titles:
            stream=mux.add_stream('pcm_f32le',rate=self.rate)
            stream.codec_context.layout='stereo' if self.channels==2 else 'mono'
            stream.codec_context.format='flt';stream.time_base=Fraction(1,self.rate)
            stream.codec_context.time_base=stream.time_base;stream.metadata['title']=title
            self.streams.append(stream)

    @property
    def late_frames(self):
        return max(timeline.late_frames for timeline in self.timelines)

    def drain(self):
        for source,timeline in zip(self.queues,self.timelines):
            while True:
                try:timestamp,data=source.get_nowait();timeline.add(timestamp,data)
                except queue.Empty:break

    def read(self,frames):
        blocks=[timeline.read(frames)[1] for timeline in self.timelines]
        if self.multitrack:
            import numpy as np
            mixed=np.zeros(frames*self.channels,dtype=np.float32)
            for block in blocks:mixed+=np.frombuffer(block,dtype='<f4')
            blocks=[np.clip(mixed,-1,1).astype('<f4').tobytes(),*blocks]
        start=self.cursor;self.cursor+=frames
        return start,blocks

    def mux(self,container,frames=1024):
        import av
        pos,blocks=self.read(frames)
        for stream,data in zip(self.streams,blocks):
            packet=av.Packet(data);packet.stream=stream
            packet.pts=packet.dts=pos;packet.duration=frames;packet.time_base=stream.time_base
            container.mux(packet)


def export_audio(info,args):
    """Return FFmpeg audio filters/maps plus expected output count and titles."""
    mode=args.get('audio_mode','all')
    if mode not in {'all','mix','game','chat','none','custom'}:raise ValueError('Неизвестный выбор аудиодорожки')
    if mode=='custom':
        selected=args.get('audio_tracks',[]);count=info['audio']
        if not isinstance(selected,list) or len(selected)>count:raise ValueError('Некорректный список дорожек')
        seen=set();filters=[]
        for position,track in enumerate(selected):
            if not isinstance(track,dict):raise ValueError('Некорректная дорожка')
            index=track.get('index');gain=track.get('gain',100)
            if type(index) is not int or not 0<=index<count or index in seen:raise ValueError('Дорожка не найдена или повторяется')
            if isinstance(gain,bool) or not isinstance(gain,(int,float)) or not 0<=gain<=100:raise ValueError('Громкость: от 0 до 100%')
            seen.add(index);filters.append(f'[0:a:{index}]volume={gain/100:.6f}[a{position}]')
        if not selected:return [],['-an'],0,[]
        if len(selected)==1:
            titles=info.get('audio_titles',[]);index=selected[0]['index']
            return ['-filter_complex',';'.join(filters)],['-map','[a0]'],1,[titles[index] if index<len(titles) else TITLES[0]]
        inputs=''.join(f'[a{i}]' for i in range(len(selected)))
        filters.append(f'{inputs}amix=inputs={len(selected)}:normalize=0:duration=longest[chosen]')
        return ['-filter_complex',';'.join(filters)],['-map','[chosen]'],1,[TITLES[0]]
    gains=[]
    for name in ('game_gain','chat_gain'):
        value=args.get(name,100)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=value<=100:raise ValueError('Громкость: от 0 до 100%')
        gains.append(value/100)
    count=info['audio']
    titles=info.get('audio_titles',[])
    # A three-track file may now be mix + device + microphone, not game + chat.
    has_microphone=titles and any('микрофон' in title.casefold() for title in titles)
    if has_microphone and mode in {'game','chat'}:
        target='Игра' if mode=='game' else 'Discord / чат'
        index=next((i for i,title in enumerate(titles) if title==target),None)
        if index is None:raise ValueError('В этом файле нет дорожки: '+target)
        gain=gains[0 if mode=='game' else 1] if mode!='mix' else 1
        return ['-filter_complex',f'[0:a:{index}]volume={gain:.6f}[selected]'],['-map','[selected]'],1,[target]
    if has_microphone and mode in {'mix','all'}:
        if count==1:return [],['-map','0:a:0'],1,titles
        if gains==[1,1]:return [],['-map','0:a?' if mode=='all' else '0:a:0'],count if mode=='all' else 1,titles if mode=='all' else [titles[0]]
        sources=list(range(1,count)) if count>1 and titles[0]=='Общий звук' else list(range(count))
        filters=[]
        for position,index in enumerate(sources):
            gain=gains[0] if titles[index]=='Игра' else gains[1] if titles[index]=='Discord / чат' else 1
            tail=f',asplit=2[m{position}][s{position}]' if mode=='all' else f'[m{position}]'
            filters.append(f'[0:a:{index}]volume={gain:.6f}'+tail)
        filters.append(''.join(f'[m{i}]' for i in range(len(sources)))+f'amix=inputs={len(sources)}:normalize=0[mix]')
        maps=['-map','[mix]']
        if mode=='all':
            for i in range(len(sources)):maps+=['-map',f'[s{i}]']
        return ['-filter_complex',';'.join(filters)],maps,1+len(sources) if mode=='all' else 1,[TITLES[0],*(titles[i] for i in sources)] if mode=='all' else [TITLES[0]]
    if mode=='none' or not count:return [],['-an'],0,[]
    if mode in {'game','chat'} and count<3:raise ValueError('В этом файле нет отдельных дорожек игры и чата')
    if mode=='all' and gains==[1,1]:return [],['-map','0:a?'],count,[]
    if count<3:return [],['-map','0:a:0'],1,[TITLES[0]]
    if mode in {'game','chat'}:
        index=1 if mode=='game' else 2;gain=gains[index-1]
        return ['-filter_complex',f'[0:a:{index}]volume={gain:.6f}[selected]'],['-map','[selected]'],1,[TITLES[index]]
    graph=(f'[0:a:1]volume={gains[0]:.6f},asplit=2[gm][game];'
           f'[0:a:2]volume={gains[1]:.6f},asplit=2[cm][chat];'
           '[gm][cm]amix=inputs=2:normalize=0[mix]')
    if mode=='mix':
        graph=(f'[0:a:1]volume={gains[0]:.6f}[game];[0:a:2]volume={gains[1]:.6f}[chat];'
               '[game][chat]amix=inputs=2:normalize=0[mix]')
        return ['-filter_complex',graph],['-map','[mix]'],1,[TITLES[0]]
    return ['-filter_complex',graph],['-map','[mix]','-map','[game]','-map','[chat]'],3,list(TITLES)
