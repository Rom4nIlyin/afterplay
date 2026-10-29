from pathlib import Path
import ast,tempfile,threading,unittest
from output_names import reserve_output,commit_output,clean_name


class OutputNameTests(unittest.TestCase):
    def test_exact_user_name_and_extension_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            with reserve_output(folder,'Мой бой & осада.mp4','.mp4') as path:
                self.assertEqual(path.name,'Мой бой & осада.mp4');self.assertFalse(path.exists())
            with reserve_output(folder,'Вертикальное видео','.mp4') as path:self.assertEqual(path.name,'Вертикальное видео.mp4')

    def test_duplicates_are_numbered_without_overwriting_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            original=Path(folder)/'Клип.mp4';original.write_bytes(b'original')
            with reserve_output(folder,'Клип','.mp4') as path:
                self.assertEqual(path.name,'Клип (2).mp4')
                with reserve_output(folder,'Клип','.mp4') as second:self.assertEqual(second.name,'Клип (3).mp4')
            self.assertEqual(original.read_bytes(),b'original')

    def test_failed_job_releases_name_without_leaving_a_placeholder(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError):
                with reserve_output(folder,'Повтор','.mp4'):raise RuntimeError('cancelled')
            self.assertEqual(list(Path(folder).iterdir()),[])
            with reserve_output(folder,'Повтор','.mp4') as path:self.assertEqual(path.name,'Повтор.mp4')

    def test_concurrent_exports_cannot_reserve_the_same_path(self):
        with tempfile.TemporaryDirectory() as folder:
            gate=threading.Barrier(4);names=[];errors=[]
            def worker():
                try:
                    with reserve_output(folder,'Клип','.mp4') as path:names.append(path.name);gate.wait(timeout=3)
                except Exception as error:errors.append(error)
            threads=[threading.Thread(target=worker) for _ in range(4)]
            for thread in threads:thread.start()
            for thread in threads:thread.join(timeout=4)
            self.assertFalse(errors);self.assertEqual(set(names),{'Клип.mp4','Клип (2).mp4','Клип (3).mp4','Клип (4).mp4'})

    def test_late_name_collision_refuses_to_replace_the_other_file(self):
        with tempfile.TemporaryDirectory() as folder:
            partial=Path(folder)/'partial.mp4';partial.write_bytes(b'new');target=Path(folder)/'Клип.mp4';target.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):commit_output(partial,target)
            self.assertEqual(target.read_bytes(),b'keep');self.assertEqual(partial.read_bytes(),b'new')

    def test_windows_invalid_characters_are_cleaned_and_reserved_names_rejected(self):
        self.assertEqual(clean_name('Мой: клип?','.mp4'),'Мой_ клип_')
        for name in ('CON','nul','COM1','LPT9.txt'):
            with self.assertRaises(ValueError):clean_name(name,'.mp4')
        self.assertLessEqual(len(clean_name('🐈'*200,'.mp4').encode('utf-16-le'))//2,180)

    def test_portable_builder_includes_name_reservations(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'scripts/build_portable.py').read_text('utf-8'))
        files=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FILES' for t in node.targets))
        self.assertIn('output_names.py',files)


class NamedExportIntegrationTests(unittest.TestCase):
    def test_mp4_gif_and_montage_use_user_names(self):
        from app import Suite,run
        import montage
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);suite=Suite(root/'data');source=root/'source.mp4'
            created=run([suite.ff(),'-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=15:duration=3','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-y',source],timeout=20)
            self.assertEqual(created.returncode,0,created.stderr);identifier=suite.index_video(source)
            args={'id':identifier,'start':0,'end':2,'name':'Мой клип','format':'original','audio_mode':'none'}
            first=suite.export(args,{});original=Path(first['path']).read_bytes();second=suite.export(args,{})
            self.assertEqual(Path(first['path']).name,'Мой клип.mp4');self.assertEqual(Path(second['path']).name,'Мой клип (2).mp4');self.assertEqual(Path(first['path']).read_bytes(),original)
            gif=suite.export({**args,'format':'gif','name':'Мой GIF.gif'},{});self.assertEqual(Path(gif['path']).name,'Мой GIF.gif')
            combined=montage.export(suite,{'name':'Моя подборка','audio_mode':'none','segments':[{'id':identifier,'start':0,'end':2}]},{})
            self.assertEqual(Path(combined['path']).name,'Моя подборка.mp4')
            self.assertFalse(list(suite.recordings_dir().glob('*.partial.*')))

if __name__=='__main__':unittest.main()
