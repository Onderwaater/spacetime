# keep this import at top to ensure proper matplotlib backend selection
from .mplfigure import MPLFigureEditor

from . import plot, util, version, uiutil
import modules

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
		return util.localtz.localize(datetime.datetime.combine(self.date, self.time))

	def _set_datetime(self, dt):
		self.date = dt.date()
		self.time = dt.time()

	def _get_mpldt(self):
		return util.mpldtfromdatetime(self.datetime)

	def _set_mpldt(self, f):
		self.datetime = util.datetimefrommpldt(f, tz=util.localtz)

	traits_view = View(
		HGroup(
			Item('time', editor=uiutil.TimeEditor()),
			Item('date'),
			show_labels=False,
	))


class PanelSelector(HasTraits):
	panelmgr = Instance(modules.PanelManager)
	selected = List(Str)
	message = Str('Select subgraph type')
	types = Tuple()

	def _types_default(self):
		return self.panelmgr.list_labels()

	traits_view = View(
		Group(
			Item('message', emphasized=True, style='readonly'),
			Item('types', editor=ListStrEditor(editable=False, multi_select=True, selected='selected')),
			show_labels=False,
			padding=5,
		),
		title='Select subgraph type',
		height=300,
		width=200,
		buttons=OKCancelButtons,
		kind='modal',
	)


class MainTab(modules.generic.panels.SerializableTab):
	xauto = Bool(True)
	not_xauto = Property(depends_on='xauto')
	xmin = Instance(DateTimeSelector, args=())
	xmax = Instance(DateTimeSelector, args=())
	xmin_mpldt = DelegatesTo('xmin', 'mpldt')
	xmax_mpldt = DelegatesTo('xmax', 'mpldt')
	label = 'Main'
	status = Str('')

	traits_saved = 'xmin_mpldt', 'xmax_mpldt', 'xauto'

	mainwindow = Any

	def _get_not_xauto(self):
		return not self.xauto

	def xlim_callback(self, ax):
		self.xmin.mpldt, self.xmax.mpldt = ax.get_xlim()

	@on_trait_change('xmin_mpldt, xmax_mpldt, xauto')
	def xlim_changed(self):
		self.mainwindow.plot.set_shared_xlim(self.xmin.mpldt, self.xmax.mpldt, self.xauto)
		self.mainwindow.update_canvas()

	def reset_autoscale(self):
		self.xauto = True

	def get_serialized(self):
		d = super(MainTab, self).get_serialized()
		d['version'] = version.version
		return d

	traits_view = View(Group(
		Group(
			Item('xauto', label='Auto'),
			Item('xmin', label='Min', style='custom', enabled_when='not_xauto'),
			Item('xmax', label='Max', style='custom', enabled_when='not_xauto'),
			label='Time axis limits',
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


class AboutWindow(HasTraits):
	title = Str('Spacetime ' + version.version)
	desc = Str('Copyright 2010-2011 Leiden University.\nWritten by Sander Roobol <roobol@physics.leidenuniv.nl>.\n\nRedistribution outside Leiden University is not permitted.')

	traits_view = View(
		Group(
			Item('title', emphasized=True, style='readonly'),
			Item('desc', style='readonly', editor=TextEditor(multi_line=True)),
			show_labels=False,
			padding=5,
		),
		title='About Spacetime',
		buttons=[OKButton],
		kind='modal',
	)


class MainWindowHandler(Handler):
	@staticmethod	
	def get_ui_title(filename = None):
		if filename is None:
			return 'Spacetime'
		else:
			return 'Spacetime - %s' % filename

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
		dlg = wx.FileDialog(info.ui.control, style=wx.FD_OPEN, wildcard='Spacetime Project files (*.spacetime)|*.spacetime')
		if dlg.ShowModal() != wx.ID_OK:
			return
		mainwindow = info.ui.context['object']
		mainwindow.clear()
		try:
			mainwindow.open_project(dlg.Path)
		except:
			uiutil.Message.file_open_failed(dlg.Path, parent=info.ui.control)
		else:
			self.set_ui_title(info, dlg.Filename)
		mainwindow.drawmgr.redraw_figure()

	def do_save(self, info):
		dlg = wx.FileDialog(info.ui.control, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT, wildcard='Spacetime Project files (*.spacetime)|*.spacetime')
		if dlg.ShowModal() != wx.ID_OK:
			return False
		mainwindow = info.ui.context['object']
		filename, path = dlg.Filename, dlg.Path
		if not path.endswith('.spacetime'):
			path += '.spacetime'
			filename += '.spacetime'
		try:
			if mainwindow.save_project(path):
				self.set_ui_title(info, filename)
				return True
		except:
			uiutil.Message.file_open_failed(path, parent=info.ui.control)
		return False

	def do_add(self, info):
		mainwindow = info.ui.context['object']
		ps = PanelSelector(panelmgr=mainwindow.panelmgr)
		#ps.types = mainwindow.panelmgr.list_labels()
		ps.edit_traits(parent=info.ui.control)

		for s in ps.selected:
			mainwindow.add_tab(mainwindow.panelmgr.get_class_by_label(s))

	def do_python(self, info):
		PythonWindow().edit_traits(parent=info.ui.control)

	def do_about(self, info):
		AboutWindow().edit_traits(parent=info.ui.control)

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
				uiutil.Message.file_save_failed(path, parent=info.ui.control)

	def do_fit(self, info):
		mainwindow = info.ui.context['object']
		with mainwindow.drawmgr.hold():
			for tab in mainwindow.tabs:
				tab.reset_autoscale()

	def do_zoom(self, info):
		mainwindow = info.ui.context['object']
		mainwindow.figure.toolbar.zoom()
		mainwindow.zoom_checked = not mainwindow.zoom_checked
		mainwindow.pan_checked = False

	def do_pan(self, info):
		mainwindow = info.ui.context['object']
		mainwindow.figure.toolbar.pan()
		mainwindow.pan_checked = not mainwindow.pan_checked
		mainwindow.zoom_checked = False


class FigureWindow(HasTraits):
	mainwindow = Any
	figure = Instance(matplotlib.figure.Figure)
	status = DelegatesTo('mainwindow')

	def on_figure_resize(self, event):
		self.mainwindow.on_figure_resize(event)

	traits_view = View(
		Group(
			Item('figure', editor=MPLFigureEditor(status='status')),
			show_labels=False,
		),
		resizable=True,
		height=700, width=1100,
		buttons=NoButtons,
		title=MainWindowHandler.get_ui_title(),
		statusbar='status',
	)


ICON_PATH = [os.path.join(os.path.dirname(__file__), 'icons')]
def GetIcon(id):
	return ImageResource(id, search_path=ICON_PATH)


class App(HasTraits):
	plot = Instance(plot.Plot)
	figure = Instance(matplotlib.figure.Figure)
	maintab = Instance(MainTab)
	status = DelegatesTo('maintab')
	drawmgr = Instance(uiutil.DrawManager)
	panelmgr = Instance(modules.PanelManager, args=())

	pan_checked = Bool(False)
	zoom_checked = Bool(False)

	tabs = List(Instance(modules.generic.panels.Tab))

	def on_figure_resize(self, event):
		self.plot.setup_margins()
		self.drawmgr.update_canvas()

	def update_canvas(self):
		wx.CallAfter(self.figure.canvas.draw)

	def add_tab(self, klass, serialized_data=None):
		tab = klass(drawmgr=self.drawmgr, autoscale=self.plot.autoscale, parent=self.ui.control)
		if serialized_data is not None:
			tab.from_serialized(serialized_data)
		self.tabs.append(tab)

	def _maintab_default(self):
		return MainTab(mainwindow=self, drawmgr=self.drawmgr)

	def _drawmgr_default(self):
		return uiutil.DrawManager(self.redraw_figure, self.update_canvas)

	def _tabs_changed(self):
		self.drawmgr.redraw_figure()

	def _tabs_items_changed(self, event):
		for removed in event.removed:
			if isinstance(removed, MainTab):
				self.tabs.insert(0, removed)
		self.drawmgr.redraw_figure()

	def _tabs_default(self):
		return [self.maintab]

	def clear(self):
		self.tabs = self._tabs_default()
		for klass in self.panelmgr.list_classes():
			klass.number = 0

	def open_project(self, path):
		with open(path, 'rb') as fp:
			if fp.read(15) != 'Spacetime\nJSON\n':
				raise ValueError('not a valid Spacetime project file')
			data = json.load(fp)
		with self.drawmgr.hold_delayed():
			self.tabs[0].from_serialized(data.pop(0)[1])
			# FIXME: check version number and emit warning
			for id, props in data:
				try:
					self.add_tab(self.panelmgr.get_class_by_id(id), props)
				except KeyError:
					pass # silently ignore unknown class names for backward and forward compatibility

	def save_project(self, path):
		data = [('general', self.tabs[0].get_serialized())]
		for tab in self.tabs:
			if isinstance(tab, panels.SubplotPanel):
				data.append((self.panelmgr.get_id_by_instance(tab), tab.get_serialized()))
		with open(path, 'wb') as fp:
			fp.write('Spacetime\nJSON\n')
			json.dump(data, fp)
		return True

	def has_modifications(self):
		return len(self.tabs) > 1

	def redraw_figure(self):
		self.plot.clear()
		[self.plot.add_subplot(tab.plot) for tab in self.tabs if isinstance(tab, modules.generic.panels.SubplotPanel) and tab.visible]
		self.plot.setup()
		self.plot.draw()
		self.plot.autoscale()

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

	main_toolbar = ToolBar(
		'main',
			Action(name='New', action='do_new', tooltip='New project', image=GetIcon('new')),
			Action(name='Open', action='do_open', tooltip='Open project', image=GetIcon('open')),
			Action(name='Save', action='do_save', tooltip='Save project', image=GetIcon('save')),
		'add',
			Action(name='Add', action='do_add', tooltip='Add graph', image=GetIcon('add')),
		'graph',
			Action(name='Fit', action='do_fit', tooltip='Zoom to fit', image=GetIcon('fit')),
			Action(name='Zoom', action='do_zoom', tooltip='Zoom rectangle', image=GetIcon('zoom'), checked_when='zoom_checked', style='toggle'),
			Action(name='Pan', action='do_pan', tooltip='Pan', image=GetIcon('pan'), checked_when='pan_checked', style='toggle'),
		'export',
			Action(name='Export', action='do_export', tooltip='Export', image=GetIcon('export')),
		'python', 
			Action(name='Python', action='do_python', tooltip='Python shell', image=GetIcon('python')),
		'about',
			Action(name='About', action='do_about', tooltip='About', image=GetIcon('about')),
		show_tool_names=False
	)

	traits_view = View(
			HSplit(
				Item('figure', width=600, editor=MPLFigureEditor(status='status'), dock='vertical'),
				Item('tabs', style='custom', editor=ListEditor(use_notebook=True, deletable=True, page_name='.label')),
				show_labels=False,
			),
			resizable=True,
			height=700, width=1100,
			buttons=NoButtons,
			title=MainWindowHandler.get_ui_title(),
			toolbar=main_toolbar,
			statusbar='status',
			handler=MainWindowHandler(),
		)

	presentation_view = View(
		Group(
			Item('tabs', style='custom', editor=ListEditor(use_notebook=True, deletable=True, page_name='.label')),
			show_labels=False,
		),
		resizable=True,
		height=700, width=700,
		buttons=NoButtons,
		title=MainWindowHandler.get_ui_title(),
		toolbar=main_toolbar,
		handler=MainWindowHandler(),
	)

	def run(self):
		import sys
		app = wx.PySimpleApp()
		if len(sys.argv) > 1 and sys.argv[1] == '--presentation':
			figwin = FigureWindow(mainwindow=self, figure=self.figure)
			figwin.edit_traits()
			self.ui = self.edit_traits(view='presentation_view')
		else:
			self.ui = self.edit_traits()
		app.MainLoop()

if __name__ == '__main__':
	app = App()
	app.run()
