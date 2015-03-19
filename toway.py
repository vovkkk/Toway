# coding: utf8
import sys, io, re, os, subprocess, locale
from PyQt4.QtCore import *
from PyQt4.QtGui import *

try: # separate icon in the Windows dock
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Toway')
except: pass

class MyWindow(QMainWindow):
    @property
    def FILES(self):
        return [unicode(f) for f in self.QSETTINGS.value('files', []).toPyObject()]

    @property
    def QSETTINGS(self):
        return QSettings(QSettings.IniFormat, QSettings.UserScope, 'Toway', 'Toway')

    def __init__(self, *args):
        QMainWindow.__init__(self, *args)
        self.resize(self.QSETTINGS.value('size', QSize(300, 500)).toSize())
        self.move(self.QSETTINGS.value('pos', QPoint(50, 50)).toPoint())
        self.setWindowTitle('Toway')
        self.setWindowIcon(QIcon('feather.png'))

        m = QWidget()
        self.setCentralWidget(m)
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        m.setLayout(layout)

        self.tasks = {}

        lv = QListWidget()
        layout.addWidget(lv)
        # print(lv.font().family())
        lv.setItemDelegate(MyDelegate(lv, lv.font().family()))
        self.lv = lv

        files = self.FILES
        if not files:
            self.hint = QLabel(u'<br><br><br><center><big>Drop some <b>file(s)</b> here!</big></center>')
            layout.addWidget(self.hint)
            self.lv.hide()
        for f in files:
            self.retrieve_stuff(f)

        self.w = QFileSystemWatcher(files)
        self.w.fileChanged.connect(lambda p: self.report(p))

        self.lv.itemPressed.connect(lambda n: self.goto_line(n))
        self.lv.itemActivated.connect(lambda n: self.goto_line(n))

        self.setStyleSheet('QListWidget{border:0px}')
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event): event.accept()

    def dropEvent(self, event):
        fn = event.mimeData().urls()[0].toLocalFile().toLocal8Bit().data()
        files = self.FILES
        for uri in event.mimeData().urls():
            fn = unicode(uri.toLocalFile().toLocal8Bit().data(), locale.getpreferredencoding())
            if fn not in files and os.path.isfile(fn):
                files.append(fn)
        self.QSETTINGS.setValue('files', files)
        for f in files:
            self.retrieve_stuff(f)
        self.w.removePaths(files)
        self.w.addPaths(files)
        if files:
            self.lv.show()
            self.hint.hide()

    def report(self, path):
        self.w.removePaths(self.FILES)
        self.retrieve_stuff(unicode(path))
        self.w.addPaths(self.FILES)

    def retrieve_stuff(self, path):
        if not os.path.exists(path):
            return 'todo: notify that file disappeared'
        try:
            with io.open(path, 'r', encoding='utf8') as p:
                self.tasks.update({path: {}})
                for i, line in enumerate(p, start=1):
                    if u'☐' in line and '@today' in line:
                        self.tasks.get(path).update({str(i): line.replace(' @today', '').lstrip(u' ☐').rstrip(' \n')})
        except Exception as e:
            return 'todo: notify that file cant be read'
        else:
            self.generate_list()

    def generate_list(self):
        # print(self.tasks.items())
        if len(self.tasks) != len(self.FILES):
            return
        self.lv.clear()
        for f in self.FILES:
            # print(type(f))
            for n, t in self.tasks.get(f).items():
                item = QListWidgetItem();
                item.setData(Qt.DisplayRole, t)
                item.setData(Qt.UserRole + 1, n)
                item.setData(Qt.UserRole + 2, f)
                item.setToolTip(f)
                self.lv.addItem(item)

    def goto_line(self, item):
        fn = unicode(item.data(Qt.UserRole + 2).toString()).encode(locale.getpreferredencoding())
        ln = unicode(item.data(Qt.UserRole + 1).toString()).encode(locale.getpreferredencoding())
        # print(fn, ln, type(fn))
        try:
            subprocess.Popen(['subl', u'%s:%s' % (fn, ln)])
        except:
            subprocess.Popen(['sublime_text', '%s:%s' % (fn, ln)])
        else:
            return 'todo: error'

    def closeEvent(self, QCloseEvent):
        self.QSETTINGS.setValue('size', self.size())
        self.QSETTINGS.setValue('pos', self.pos())
        qApp.quit()


class MyDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, *args):
        QStyledItemDelegate.__init__(self, parent)
        self.font = u'%s' % args

    def paint(self, painter, option, index):
        QApplication.style().drawControl(QStyle.CE_ItemViewItem, option, painter, QListWidget())
        painter.save()

        title = index.data(Qt.DisplayRole).toString()
        r = option.rect.adjusted(15, 0, -10, -20);
        # painter.setFont(QFont(self.font, 0, QFont.DemiBold))
        painter.drawText(r.left(), r.top(), r.width(), r.height(), Qt.AlignBottom|Qt.AlignLeft, title)

        descr = index.data(Qt.UserRole + 1).toString()
        r = option.rect.adjusted(15, 20, -10, 0);
        # painter.setFont(QFont(self.font, 0, QFont.Light))
        # painter.setFont(QApplication.font())
        painter.setOpacity(0.25)
        painter.drawText(r.left(), r.top(), r.width(), r.height(), Qt.AlignLeft, descr)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(-1, 40)


def main():
    app = QApplication(sys.argv)
    w = MyWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()