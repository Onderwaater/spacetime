# keep this import at top to ensure proper matplotlib backend selection
from mplfigure import MPLFigureEditor

from . import plot, util, panels, version, uiutil

from enthought.traits.api import *
from enthought.traits.ui.api import *
from enthought.pyface.api import ImageResource
import matplotlib.figure, matplotlib.transforms
import wx
import datetime
import json
import os


class DateTimeSelector(HasTraits):
	date = Date(datetime.date.today())
	time = Time(datetime.time())
	datetime = Property(depends_on='date, time')
	mpldt = Property(depends_on='datetime')

	def _get_datetime(self):
		return datetime.datetime.combine(self.date, self.time)

	def _set_datetime(self, dt):
		self.date = dt.date()
		self.time = dt.time()

	def _get_mpldt(self):
		return util.mpldtfromdatetime(self.datetime)

	def _set_mpldt(self, f):
		self.datetime = util.datetimefrommpldt(f)

	traits_view = View(
		HGroup(
			Item('time', editor=TimeEditor(strftime='%H:%M:%D')),
			Item('date'),
			show_labels=False,
	))


class PanelMapper(object):
	MAPPING = (
		('camera',              panels.CameraFramePanel),
		('cameratrend',         panels.CameraTrendPanel),
		('quaderaqms',          panels.QMSPanel),
		('lpmgascabinet',       panels.GasCabinetPanel),
		('prototypegascabinet', panels.OldGasCabinetPanel),
		('reactorenvironment',  panels.ReactorEnvironmentPanel),
		('tpdirk',              panels.TPDirkPanel),
		('cameracv',            panels.CVPanel),
	)

	list_classes = tuple(klass for (id, klass) in MAPPING if id != 'general')
	list_tablabels = tuple(klass.tablabel for klass in list_classes)
	
	mapping_id_class = dict((id, klass) for (id, klass) in MAPPING)
	mapping_classname_id = dict((klass.__name__, id) for (id, klass) in MAPPING)
	mapping_tablabel_class = dict((klass.tablabel, klass) for klass in list_classes)

	@classmethod
	def get_class_by_id(klass, id):
		return klass.mapping_id_class[id]

	@classmethod
	def get_id_by_instance(klass, obj):
		return klass.mapping_classname_id[obj.__class__.__name__]

	@classmethod
	def get_class_by_tablabel(klass, label):
		return klass.mapping_tablabel_class[label]


class MainTab(panels.SerializableTab):
	xmin = Instance(DateTimeSelector, args=())
	xmax = Instance(DateTimeSelector, args=())
	xmin_mpldt = DelegatesTo('xmin', 'mpldt')
	xmax_mpldt = DelegatesTo('xmax', 'mpldt')
	tablabel = 'Main'
	status = Str('')

	traits_saved = 'xmin_mpldt', 'xmax_mpldt'

	add = Button()
	subgraph_type = Enum(*PanelMapper.list_tablabels)

	mainwindow = Any

	def _add_fired(self):
		self.mainwindow.add_tab(PanelMapper.get_class_by_tablabel(self.subgraph_type))
	
	def xlim_callback(self, ax):
		self.xmin.mpldt, self.xmax.mpldt = ax.get_xlim()

	@on_trait_change('xmin.mpldt')
	def _xmin_mpldt_changed(self):
		if self.mainwindow.plot.master_axes and self.mainwindow.plot.master_axes.get_xlim()[0] != self.xmin.mpldt:
			self.mainwindow.plot.master_axes.set_xlim(xmin=self.xmin.mpldt)
			self.mainwindow.update_canvas()

	@on_trait_change('xmax.mpldt')
	def _xmax_mpldt_changed(self):
		if self.mainwindow.plot.master_axes and self.mainwindow.plot.master_axes.get_xlim()[1] != self.xmax.mpldt:
			self.mainwindow.plot.master_axes.set_xlim(xmax=self.xmax.mpldt)
			self.mainwindow.update_canvas()

	def get_serialized(self):
		d = super(MainTab, self).get_serialized()
		d['version'] = version.version
		return d

	traits_view = View(Group(
		Group(
			Item('xmin', style='custom'),
			Item('xmax', style='custom'),
			label='Graph settings',
			show_border=True,
		),
		Group(
			Item('subgraph_type', show_label=False, style='custom', editor=EnumEditor(values=PanelMapper.list_tablabels, format_func=lambda x: x, cols=1)),
			Item('add', show_label=False),
			label='Add subgraph',
			show_border=True,
		),
		Group(
			Item('status', show_label=False, style='readonly'),
			label='Cursor',
			show_border=True,
		),
		layout='normal',
	))


class PythonWindow(HasTraits):
	shell = PythonValue({})
	traits_view = View(
		Item('shell', show_label=False, editor=ShellEditor(share=False)),
		title='Python shell',
		height=600,
		width=500,
	)


class MainWindowHandler(Handler):
	@staticmethod	
	def get_ui_title(filename = None):
		title = 'Spacetime %s' % version.version
		if filename is not None:
			title = '%s - %s' % (title, filename)
		return title

	def set_ui_title(self, info, filename=None):
		info.ui.title = self.get_ui_title(filename)

	def do_new(self, info):
		if not self.close(info):
			return False
		mainwindow = info.ui.context['object']
		mainwindow.clear()
		self.set_ui_title(info)
		return True

	def close(self, info, is_ok=None):
		mainwindow = info.ui.context['object']
		if mainwindow.has_modifications():
			dlg = wx.MessageDialog(info.ui.control, 'Save current project?', style=wx.YES_NO | wx.CANCEL | wx.ICON_EXCLAMATION)
			ret = dlg.ShowModal()
			if ret == wx.ID_CANCEL:
				return False
			elif ret == wx.ID_YES:
				return self.do_save(info)
		return True
		
	def do_open(self, info):
		if not self.close(info):
			return
		dlg = wx.FileDialog(info.ui.control, style=wx.FD_OPEN, wildcard='Spacetime Project files (*.stp)|*.stp')
		if dlg.ShowModal() != wx.ID_OK:
			return
		mainwindow = info.ui.context['object']
		mainwindow.clear()
		self.set_ui_title(info, dlg.Filename)
		fp = open(dlg.Path)
		data = json.load(fp)
		fp.close()
		mainwindow.tabs[0].from_serialized(data.pop(0)[1])
		# FIXME: check version number and emit warning
		for id, props in data:
			try:
				mainwindow.add_tab(PanelMapper.get_class_by_id(id), props)
			except KeyError:
				pass # silently ignore unknown class names for backward and forward compatibility
		mainwindow.redraw_figure()

	def do_save(self, info):
		dlg = wx.FileDialog(info.ui.control, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT, wildcard='Spacetime Project files (*.stp)|*.stp')
		if dlg.ShowModal() != wx.ID_OK:
			return False
		mainwindow = info.ui.context['object']

		data = [('general', mainwindow.tabs[0].get_serialized())]
		for tab in mainwindow.tabs:
			if isinstance(tab, panels.SubplotPanel):
				data.append((PanelMapper.get_id_by_instance(tab), tab.get_serialized()))
		try:
			fp = open(dlg.Path, 'w')
			json.dump(data, fp)
			fp.close()
		except:
			uiutil.Message.file_save_failed(path)
			return False
		self.set_ui_title(info, dlg.Filename)
		return True

	def do_python(self, info):
		PythonWindow().edit_traits()

	def do_export(self, info):
		# mostly borrowed from Matplotlib's NavigationToolbar2Wx.save()
		mainwindow = info.ui.context['object']
		canvas = mainwindow.figure.canvas
		# Fetch the required filename and file type.
		filetypes, exts, filter_index = canvas._get_imagesave_wildcards()
		default_file = "image." + canvas.get_default_filetype()
		dlg = wx.FileDialog(info.ui.control, "Save to file", "", default_file, filetypes, wx.SAVE|wx.OVERWRITE_PROMPT)
		dlg.SetFilterIndex(filter_index)
		if dlg.ShowModal() == wx.ID_OK:
			dirname  = dlg.GetDirectory()
			filename = dlg.GetFilename()
			format = exts[dlg.GetFilterIndex()]
			basename, ext = os.path.splitext(filename)
			if ext.startswith('.'):
				ext = ext[1:]
			if ext in ('svg', 'pdf', 'ps', 'eps', 'png') and format != ext:
				#looks like they forgot to set the image type drop down, going with the extension.
				#warnings.warn('extension %s did not match the selected image type %s; going with %s'%(
				format = ext
			path = os.path.join(dirname, filename)
			try:
				canvas.print_figure(path, format=format)
			except:
				uiutil.Message.file_save_failed(path)


ICON_PATH = [os.path.join(os.path.dirname(__file__), 'icons')]
def GetIcon(id):
	return ImageResource(id, search_path=ICON_PATH)


class App(HasTraits):
	plot = Instance(plot.Plot)
	figure = Instance(matplotlib.figure.Figure)
	maintab = Instance(MainTab)
	status = DelegatesTo('maintab')

	tabs = List(Instance(panels.Tab))

	def on_figure_resize(self, event):
		self.plot.setup_margins()
		self.update_canvas()

	def update_canvas(self):
		wx.CallAfter(self.figure.canvas.draw)

	def add_tab(self, klass, serialized_data=None):
		tab = klass(update_canvas=self.update_canvas, autoscale=self.plot.autoscale, redraw_figure=self.redraw_figure)
		if serialized_data is not None:
			tab.hold = True
			tab.from_serialized(serialized_data)
			tab.hold = False
		self.tabs.append(tab)

	def _maintab_default(self):
		return MainTab(mainwindow=self)

	def _tabs_changed(self):
		self.redraw_figure()

	def _tabs_items_changed(self, event):
		for removed in event.removed:
			if isinstance(removed, MainTab):
				self.tabs.insert(0, removed)
		self.redraw_figure()

	def _tabs_default(self):
		return [self.maintab]

	def clear(self):
		self.tabs = self._tabs_default()
		for klass in PanelMapper.list_classes:
			klass.number = 0

	def has_modifications(self):
		return len(self.tabs) > 2

	def redraw_figure(self):
		self.plot.clear()
		[self.plot.add_subplot(tab.plot) for tab in self.tabs if isinstance(tab, panels.SubplotPanel) and tab.visible]
		self.plot.setup()
		self.plot.draw()
		self.plot.autoscale()
		self.update_canvas()

	def _plot_default(self):
		p = plot.Plot.newmatplotlibfigure()
		p.setup()

		# At this moment, the figure has not yet been initialized properly, so delay these calls.
		# This has to be a lambda statement to make a closure on the variables 'p' and 'self'
		wx.CallAfter(lambda: (
						p.figure.canvas.mpl_connect('resize_event', self.on_figure_resize), 
						p.set_xlim_callback(self.maintab.xlim_callback)
		))
		return p

	def _figure_default(self):
		return self.plot.figure

	traits_view = View(
			HSplit(
				Item('figure', editor=MPLFigureEditor(status='status'), dock='vertical'),
				Item('tabs', style='custom', width=200, editor=ListEditor(use_notebook=True, deletable=True, page_name='.tablabel')),
				show_labels=False,
			),
			resizable=True,
			height=700, width=1100,
			buttons=NoButtons,
			title=MainWindowHandler.get_ui_title(),
			toolbar=ToolBar(
				'main',
					Action(name='New', action='do_new', tooltip='New project', image=GetIcon('new')),
					Action(name='Open', action='do_open', tooltip='Open project', image=GetIcon('open')),
					Action(name='Save', action='do_save', tooltip='Save project', image=GetIcon('save')),
				'add',
					Action(name='Add', action='do_add', tooltip='Add graph', image=GetIcon('add')),
				'graph',
					Action(name='Fit', action='do_fit', tooltip='Zoom to fit', image=GetIcon('fit')),
					Action(name='Zoom', action='do_zoom', tooltip='Zoom rectangle', image=GetIcon('zoom')),
					Action(name='Pan', action='do_pan', tooltip='Pan', image=GetIcon('pan')),
				'export',
					Action(name='Export', action='do_export', tooltip='Export', image=GetIcon('export')),
				'python', 
					Action(name='Python', action='do_python', tooltip='Python shell', image=GetIcon('python')),
				show_tool_names=False
			),
			handler=MainWindowHandler()
		)

	def run(self):
		self.configure_traits()


if __name__ == '__main__':
	app = App()
	app.run()
