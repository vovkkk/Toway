# coding: utf8
import sys, io, re, os, subprocess, locale
from PyQt4.QtCore import *
from PyQt4.QtGui import *

try: # separate icon in the Windows dock
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Toway')
except: pass

TASK   = re.compile(ur'(?ixu)^\s*(-|❍|❑|■|□|☐|▪|▫|–|—|\[\s\])(\s+.*)')
IGNORE = ['@done', '@cancelled', '@canceled']
TAGS   = ['@today', '@important', '@critical', '@bug']

PATH = Qt.UserRole + 2
LINE = Qt.UserRole + 3


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
        self.setWindowIcon(QIcon('icons/swap.svg'))

        m = QWidget()
        self.setCentralWidget(m)
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        m.setLayout(layout)

        self.tasks, self.stats = {}, {}

        tasks_list = QListWidget()
        layout.addWidget(tasks_list)
        # print(tasks_list.font().family())
        tasks_list.setItemDelegate(MyDelegate(tasks_list, tasks_list.font().family()))
        self.tasks_list = tasks_list

        self.files_list = QListWidget()
        layout.addWidget(self.files_list)
        self.files_list.setItemDelegate(MyDelegate(self.files_list, tasks_list.font().family()))
        self.files_list.hide()

        files = self.FILES
        self.hint = QLabel(u'<br><br><br><center><img src="icons/drop.png"><br><br><big>Drop<br>some <b>file(s)</b><br>here!</big></center><br>')
        if not files:
            layout.addWidget(self.hint)
            # self.tasks_list.hide()
        for f in files:
            self.retrieve_stuff(f)

        self.w = QFileSystemWatcher(files)
        self.w.fileChanged.connect(lambda p: self.report(p))

        self.tasks_list.itemPressed.connect(lambda n: self.goto_line(n))
        self.tasks_list.itemActivated.connect(lambda n: self.goto_line(n))
        self.files_list.itemPressed.connect(lambda n: self.goto_line(n))
        self.files_list.itemActivated.connect(lambda n: self.goto_line(n))

        self.setStyleSheet('QListWidget{border:0px}'
                           'QToolBar{border: 0px; margin: 5px; spacing: 5px}'
                           'QPushButton{padding: 5px 10px}')
        self.setAcceptDrops(True)

        self.create_toolbar()

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
            self.tasks_list.show()
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
                self.stats.update({path: {'pending': 0, 'important': 0}})
                pending = important = 0
                for i, line in enumerate(p, start=1):
                    suitable = not any(s in s for s in IGNORE if s in line)
                    task = TASK.match(line.rstrip(' \n'))
                    if suitable and task:
                        pending += 1
                        self.stats.get(path).update(pending=pending)
                        if any(s for s in TAGS if s in line):
                            important += 1
                            tags_regex = '(%s)' % u'|'.join(TAGS)
                            text = task.group(2)
                            task = re.sub(tags_regex, '', text).lstrip().rstrip(' \n')
                            tags = sorted([t.lstrip('@') for t in re.findall(tags_regex, text)])
                            self.stats.get(path).update(important=important)
                            self.tasks.get(path).update({str(i): (task, tags)})
        except Exception as e:
            return 'todo: notify that file cant be read'
        else:
            self.generate_list()

    def generate_list(self):
        # TODO: bring part of self.show_files here
        # print(self.tasks.items())
        if len(self.tasks) != len(self.FILES):
            return
        self.tasks_list.clear()
        for f in self.FILES:
            # print(type(f))
            for n, t in self.tasks.get(f).items():
                item = QListWidgetItem()
                item.setData(Qt.DisplayRole, t[0])
                item.setData(Qt.UserRole + 1, '%s' % u', '.join(t[1]))
                item.setData(PATH, f)
                item.setData(LINE, n)
                item.setToolTip(u'<br>{0}<br><br>line {1} in {3}<br>{2}<br>'.format(t[0], n, *os.path.split(os.path.normpath(f))))
                self.tasks_list.addItem(item)

    def goto_line(self, item):
        fn = unicode(item.data(PATH).toString()).encode(locale.getpreferredencoding())
        ln = unicode(item.data(LINE).toString()).encode(locale.getpreferredencoding())
        # print(fn, ln, type(fn))
        try:
            subprocess.Popen(['subl', u'%s:%s' % (fn, ln)])
        except:
            subprocess.Popen(['sublime_text', '%s:%s' % (fn, ln)])
        else:
            return 'todo: error'

    def create_toolbar(self):
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        spacerl = QWidget()
        spacerl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        spacerr = QWidget()
        spacerr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.tasks_btn = QPushButton(QIcon('icons/bookmarks.svg'), '')
        self.tasks_btn.setToolTip('Tasks')
        self.tasks_btn.pressed.connect(self.show_tasks)

        self.files_btn = QPushButton(QIcon('icons/documents.svg'), '')
        self.files_btn.setToolTip('Files')
        self.files_btn.pressed.connect(self.show_files)

        # self.filter_btn   = QPushButton('Filter')
        # self.settings_btn = QPushButton('Settings')
        # for b in (spacerl, self.tasks_btn, self.files_btn, self.filter_btn, self.settings_btn, spacerr):
        for b in (spacerl, self.tasks_btn, self.files_btn, spacerr):
            self.toolbar.addWidget(b)
        self.addToolBar(0x4, self.toolbar)

    def show_tasks(self):
        self.files_list.hide()
        self.tasks_list.show()

    def show_files(self):
        self.tasks_list.hide()
        self.files_list.clear()
        for f in sorted(self.FILES):
            fn = os.path.split(f)[1].split('.')
            item = QListWidgetItem()
            item.setData(Qt.DisplayRole, fn[0])
            item.setData(Qt.UserRole + 1, str(self.stats.get(f)['important']) + ' out of ' + str(self.stats.get(f)['pending']) + ', ' + '.'.join(fn[1:]))
            item.setData(PATH, f)
            item.setData(LINE, 0)
            item.setToolTip(os.path.normpath(f))
            self.files_list.addItem(item)
        self.files_list.show()

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