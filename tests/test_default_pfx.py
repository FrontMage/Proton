import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest


spec = importlib.util.spec_from_file_location('default_pfx', Path(__file__).parents[1] / 'default_pfx.py')
default_pfx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(default_pfx)


class DriverHostPackagingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prefix = self.root / 'default_pfx'
        self.system32 = self.prefix / 'drive_c/windows/system32'
        self.system32.mkdir(parents=True)
        self.dist = self.root / 'files'
        self.libdir = self.dist / 'lib/wine/x86_64-windows'
        self.libdir.mkdir(parents=True)

    def source(self, machine=0x8664, builtin=True):
        raw = bytearray(256)
        raw[:2] = b'MZ'
        struct.pack_into('<I', raw, 0x3c, 0x80)
        if builtin:
            raw[0x40:0x50] = b'Wine builtin DLL'
        raw[0x80:0x84] = b'PE\0\0'
        struct.pack_into('<H', raw, 0x84, machine)
        source = self.libdir / 'winedevice.exe'
        source.write_bytes(raw)
        return source

    def test_packages_exact_same_build_host_and_relative_prefix_link(self):
        source = self.source()
        native = self.system32 / 'winedevice.exe'
        native.write_bytes(b'preserve native ARM64 host')
        default_pfx.setup_arm64_driver_host(str(self.prefix), str(self.dist))
        alias = self.libdir / 'winedevice-x64.exe'
        self.assertEqual(alias.read_bytes(), source.read_bytes())
        link = self.system32 / alias.name
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), alias.resolve())
        self.assertFalse(Path(link.readlink()).is_absolute())
        self.assertEqual(native.read_bytes(), b'preserve native ARM64 host')

    def test_repeated_packaging_refreshes_readonly_alias(self):
        source = self.source()
        source.chmod(0o444)
        for _ in range(2):
            default_pfx.setup_arm64_driver_host(str(self.prefix), str(self.dist))
        self.assertEqual((self.system32 / 'winedevice-x64.exe').read_bytes(), source.read_bytes())

    def test_rejects_wrong_architecture_and_non_builtin(self):
        for machine, builtin in ((0xaa64, True), (0x14c, True), (0x8664, False)):
            with self.subTest(machine=machine, builtin=builtin):
                self.source(machine, builtin)
                with self.assertRaises(RuntimeError):
                    default_pfx.setup_arm64_driver_host(str(self.prefix), str(self.dist))
                self.assertFalse((self.libdir / 'winedevice-x64.exe').exists())

    def test_rejects_missing_source(self):
        with self.assertRaises(RuntimeError):
            default_pfx.setup_arm64_driver_host(str(self.prefix), str(self.dist))


if __name__ == '__main__':
    unittest.main()
