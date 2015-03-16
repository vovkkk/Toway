# coding: utf8
import sys, io, re, os, subprocess
from PyQt4.QtCore import *
from PyQt4.QtGui import *

try: # separate icon in the Windows dock
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Toway')
except: pass


class MyWindow(QMainWindow):
    @property
    def SETTINGS(self):
        return {'files': [u'D:\\Dropbox\\mine\\notes-md\\ToDoAndNB\\TODO.todolist.txt']}
        # return {'files': [u'D:\\dev\\GitHub\\Toway\\todo']}

    @property
    def QSETTINGS(self):
        return QSettings(QSettings.IniFormat, QSettings.UserScope, 'Toway', 'Toway')

    def __init__(self, *args):
        QMainWindow.__init__(self, *args)
        self.resize(self.QSETTINGS.value('size', QSize(300, 500)).toSize())
        self.move(self.QSETTINGS.value('pos', QPoint(50, 50)).toPoint())
        self.setWindowTitle('Toway')
        self.setWindowIcon(QIcon('feather.png'))
        self.tasks = {}

        lv = QListWidget()
        self.setCentralWidget(lv)
        # print(lv.font().family())
        lv.setItemDelegate(MyDelegate(lv, lv.font().family()))
        self.lv = lv

        files = self.SETTINGS.get('files')
        for f in files:
            self.retrive_stuff(f)

        self.w = QFileSystemWatcher(files)
        self.w.fileChanged.connect(lambda p: self.report(p))

        self.lv.itemPressed.connect(lambda n: self.goto_line(n))
        self.lv.itemActivated.connect(lambda n: self.goto_line(n))

        self.setStyleSheet('QListWidget{border:0px}')

    def report(self, path):
        self.w.removePaths(self.SETTINGS.get('files'))
        self.retrive_stuff(path)
        self.w.addPaths(self.SETTINGS.get('files'))

    def retrive_stuff(self, path):
        if not os.path.exists(unicode(path)):
            return 'todo: notify that file disappeared'
        try:
            with io.open(unicode(path), 'r', encoding='utf8') as p:
                for i, line in enumerate(p, start=1):
                    if u'☐' in line and '@today' in line:
                        self.tasks.update({str(i): line.replace(' @today', '').lstrip(u' ☐').rstrip(' \n')})
        except Exception as e:
            return 'todo: notify that file cant be read'
        else:
            self.generate_list()

    def generate_list(self):
        # print(self.tasks.items())
        self.lv.clear()
        for n, t in self.tasks.items():
            item = QListWidgetItem();
            item.setData(Qt.DisplayRole, t)
            item.setData(Qt.UserRole + 1, n)
            item.setData(Qt.UserRole + 2, self.SETTINGS.get('files')[0])
            self.lv.addItem(item)

    def goto_line(self, item):
        fn = unicode(item.data(Qt.UserRole + 2).toString())
        ln = unicode(item.data(Qt.UserRole + 1).toString())
        # print(fn, ln)
        try:
            subprocess.Popen(['subl', u'%s:%s' % (fn, ln)])
        except:
            subprocess.Popen(['sublime_text', u'%s:%s' % (fn, ln)])
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