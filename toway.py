# coding: utf8
import sys, io, re, os
import sip  # make Qt API return normal unicode type instead of QString type
sip.setapi('QString', 2)
from PyQt4.QtCore import *
from PyQt4.QtGui import *

try:  # separate icon in the Windows dock
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Toway')
except: pass


TASK   = re.compile(ur'(?ixu)^\s*(-|❍|❑|■|□|☐|▪|▫|–|—|\[\s\])(\s+.*)')
IGNORE = ['@done', '@cancelled', '@canceled']
TAGS   = ['@today', '@important', '@critical', '@bug']
TAGS_REGEX = '(?<=\s)\@(?![\s\(])[\w\d\.\(\)\-!? :\+]+[ \t]*'
DRAW_TAGS = [t.lstrip('@') for t in TAGS]

'''tag: [background, font opacity]; background = (r, g, b, a)'''
COLOURS = {'today':     [(0,   177,  89,  99), 0.5],   # green
           'important': [(243, 119,  53, 155), 0.5],   # orange
           'critical':  [(209,  17,  65, 255), 0.5],   # red
           'bug':       [(114,   0, 172,  99), 0.5]}   # violet
'''other good colours
    37, 115, 236    blue
    0, 174, 219     light blue
    236, 9, 140     pink
    255, 196, 37    yellow
'''

# data roles for item data, used to open in ST on click item
PATH = Qt.UserRole + 2
LINE = Qt.UserRole + 3

'''data of each item has 4 roles, we shall set (item data is kinda like dictionary in Python http://pyqt.sourceforge.net/Docs/PyQt4/qt.html#ItemDataRole-enum):
    visible in main ui
        1. DisplayRole   title, task text without tags in tasklist,
                    or   filename without extension in filelist
        2. UserRole + 1  all tags as one string, separated by \v in tasklist,
                    or   amount of tasks and extension in filelist
    visible in tooltip
        3. PATH          file path which contains the task
        4. LINE          1-based line number of task, always 0 in filelist to preserve selection(s) if file was already open
'''


class MyWindow(QMainWindow):
    @property
    def FILES(self):
        return self.QSETTINGS.value('files', []).toPyObject()

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
        layout.setContentsMargins(0, 0, 0, 0)
        m.setLayout(layout)

        self.tasks, self.stats = {}, {}

        tasks_list = QListWidget()
        layout.addWidget(tasks_list)
        # print(tasks_list.font().family())
        tasks_list.setItemDelegate(MyDelegate(tasks_list))
        self.tasks_list = tasks_list

        self.files_list = QListWidget()
        layout.addWidget(self.files_list)
        self.files_list.setItemDelegate(MyDelegate(self.files_list))
        self.files_list.hide()

        files = self.FILES
        self.hint = QLabel(u'<br><br><br><center><img src="icons/drop.png"><br><br><big>Drop<br>some <b>file(s)</b><br>here!</big></center><br>')
        if not files:
            layout.addWidget(self.hint)
            self.tasks_list.hide()

        self.w = QFileSystemWatcher(files)
        self.report()
        self.w.fileChanged.connect(lambda p: self.report([p]))

        self.tasks_list.itemPressed.connect(self.goto_line)
        self.tasks_list.itemActivated.connect(self.goto_line)
        self.files_list.itemPressed.connect(self.goto_line)
        self.files_list.itemActivated.connect(self.goto_line)

        self.setStyleSheet('QListWidget{border:0px}'
                           'QToolBar{border: 0px; margin: 5px; spacing: 5px}'
                           'QPushButton{padding: 5px 10px}')
        self.setAcceptDrops(True)

        self.create_toolbar()

    def dragEnterEvent(self, event): event.accept()

    def dropEvent(self, event):
        files = self.FILES
        for uri in event.mimeData().urls():
            fn = uri.toLocalFile()
            if fn not in files and os.path.isfile(fn):
                files.append(fn)
        self.QSETTINGS.setValue('files', files)
        if files:
            self.report(files)
            self.tasks_list.show()
            self.hint.hide()
            self.files_list.hide()
            self.tasks_btn.setEnabled(True)
            self.files_btn.setEnabled(True)

    def report(self, paths=None):
        '''paths list of files (usually just one file) which were changed on filesystem'''
        files = paths or self.FILES
        self.w.removePaths(files)
        self.errors = []
        for f in files:
            self.try_to_retrieve(f)
        self.generate_list()
        self.w.addPaths(files)
        if self.errors:
            QMessageBox.critical(self, 'Toway', u'<br><br>'.join(self.errors))

    def try_to_retrieve(self, path):
        try:
            self.retrieve_stuff(path)
        except Exception as e:
            print('fail to read', str(e), path)
            self.errors.append(u'%s<br>%s' % (e.strerror, e.filename))

    def retrieve_stuff(self, path):
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
                        text = task.group(2)
                        task = re.sub(TAGS_REGEX, '', text).strip(' \n')
                        tags = sorted([t.strip('@ ') for t in re.findall(TAGS_REGEX, text)])
                        self.stats.get(path).update(important=important)
                        self.tasks.get(path).update({str(i): (task, text, tags)})

    def generate_list(self):
        self.files_list.clear()
        self.tasks_list.clear()
        for f in sorted(self.FILES):
            self.file_item(f)
            for n, t in sorted(self.tasks.get(f).items()):
                self.task_item(f, n, t)
        self.set_title()

    def set_title(self):
        count_tasks = sum(len(d) for d in self.tasks.values())
        if count_tasks:
            self.setWindowTitle('Toway (%d)' % count_tasks)
        else:
            self.setWindowTitle('Toway')

    def task_item(self, fpath, linen, task):
        task, text, tags = task
        item = QListWidgetItem()
        item.setData(Qt.DisplayRole, task)
        item.setData(Qt.UserRole + 1, '%s' % u'\v'.join(tags))
        item.setData(PATH, fpath)
        item.setData(LINE, linen)
        item.setData(Qt.ToolTipRole, u'<br>{0}<br><br>line {1} in {3}<br>{2}<br>'.format(text, linen, *os.path.split(os.path.normpath(fpath))))
        self.tasks_list.addItem(item)

    def file_item(self, fpath):
        fn = os.path.split(fpath)[1].split('.')
        item = QListWidgetItem()
        item.setData(Qt.DisplayRole, fn[0])
        item.setData(Qt.UserRole + 1, u'%d out of %d, %s' % (self.stats.get(fpath)['important'], self.stats.get(fpath)['pending'], u'.'.join(fn[1:])))
        item.setData(PATH, fpath)
        item.setData(LINE, 0)
        item.setToolTip(os.path.normpath(fpath))
        self.files_list.addItem(item)

    def goto_line(self, item):
        fn = item.data(PATH).toString()
        ln = item.data(LINE).toString()
        # print(fn, ln, type(fn))
        args = [u'%s:%s' % (fn, ln)]
        caller = QProcess()
        success = caller.startDetached('subl', args)
        if not success:
            success = caller.startDetached('sublime_text', args)
            if not success:
                QMessageBox.critical(self, 'Sublime Text is not in system PATH', 'To make it work, ensure that Sublime Text is in PATH,<br>callable by <code>subl</code> or <code>sublime_text</code>.<br><br>Note, .bashrc (and similar) <b>does not change</b> system PATH.')

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

        if not self.FILES:
            self.tasks_btn.setDisabled(True)
            self.files_btn.setDisabled(True)

        for b in (spacerl, self.tasks_btn, self.files_btn, spacerr):
            self.toolbar.addWidget(b)
        self.addToolBar(0x4, self.toolbar)

    def show_tasks(self):
        self.files_list.hide()
        self.tasks_list.show()

    def show_files(self):
        self.tasks_list.hide()
        self.files_list.show()

    def closeEvent(self, QCloseEvent):
        self.QSETTINGS.setValue('size', self.size())
        self.QSETTINGS.setValue('pos', self.pos())
        qApp.quit()


class MyDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, *args):
        QStyledItemDelegate.__init__(self, parent)
        self.FONT = parent.font()
        self.METRICS = QFontMetrics(self.FONT)
        self.h = h = self.METRICS.height()
        self.height = h*2 + h/5 + h*2/3
        self.external_margin = h/3
        self.internal_margin = h + h/5 + self.external_margin

    def paint(self, painter, option, index):
        u'''adjusted(
                 left margin   == font height e.g. 15px,
                 top margin    == ⅓ font height,
                 right margin does not matter e.g. -10px,
                 bottom margin == -(top one [+ offset for second line])
                 )
        let offset between 1st & 2nd rows be height/5
        if height=15 then item = 5 + 15 + 3 + 15 + 5 = 43
        '''
        QApplication.style().drawControl(QStyle.CE_ItemViewItem, option, painter, QListWidget())
        painter.save()

        title = index.data(Qt.DisplayRole).toString()
        r = option.rect.adjusted(self.h, self.external_margin, self.METRICS.width(title), -self.internal_margin)
        painter.drawText(r.left(), r.top(), r.width(), r.height(), Qt.AlignBottom | Qt.AlignLeft, title)

        tags = index.data(Qt.UserRole + 1).toString().split('\v')
        offset = self.h
        for tag in tags:
            if tag in DRAW_TAGS:
                colour, opacity = COLOURS.get(tag, [option.backgroundBrush, 0.5])
                painter.setBackgroundMode(1)
                painter.setBackground(QColor(*colour))
                painter.setOpacity(opacity)
                tag = u' %s ' % tag
            else:
                painter.setBackgroundMode(0)
                painter.setOpacity(0.25)
            width = self.h + self.METRICS.width(tag)
            r = option.rect.adjusted(offset, self.internal_margin, width, self.external_margin)
            painter.drawText(r.left(), r.top(), r.width(), r.height(), Qt.AlignLeft, tag)
            offset += width

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(-1, self.height)


def main():
    app = QApplication(sys.argv)
    w = MyWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
