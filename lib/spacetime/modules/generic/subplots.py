# This file is part of Spacetime.
#
# Copyright (C) 2010-2012 Leiden University.
# Written by Sander Roobol.
#
# Spacetime is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Spacetime is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division

import numpy
import matplotlib.patches, matplotlib.cm, matplotlib.colors, matplotlib.dates, matplotlib.font_manager, matplotlib.transforms

from ... import util

class AxesRequirements(object):
	independent_x = False
	size = 1
	twinx = False
	
	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)

class Subplot(object):
	axes = None
	time_offset = 0.
	time_factor = 1.
	size = 1

	def __init__(self, data=None):
		self.data = data

	def set_data(self, data):
		self.data = data

	def get_axes_requirements(self):
		return [AxesRequirements(size=self.size)] # request a single subplot

	def set_axes(self, axes):
		self.axes = axes[0]

	def setup(self):
		# what could possibly go wrong? a lot, but it will do the right thing most of the time
		if not any(i.independent_x for i in self.get_axes_requirements()):
			self.axes.fmt_xdata = matplotlib.dates.DateFormatter('%Y-%m-%d %H:%M:%S.%f', util.localtz)

	def draw(self):
		raise NotImplementedError

	def clear(self, quick=False):
		# The quick parameter is set when the entire figure is being cleared;
		# in this case it is sufficient to only clear the internal state of the
		# Subplot and leave the axes untouched
		pass

	@staticmethod
	def autoscale_x(axes):
		# FIXME: Look at Axes.autoscale_view (line 1761) in matplotlib/axes.py
		# See also Plot.autoscale_x_shared
		xshared = axes._shared_x_axes.get_siblings(axes)
		dl = [ax.dataLim for ax in xshared if ax.lines or ax.images or ax.patches]
		if dl:
			bb = matplotlib.transforms.BboxBase.union(dl)
			x0, x1 = bb.intervalx
		else:
			x0, x1 = 0, 1
		XL = axes.xaxis.get_major_locator().view_limits(x0, x1)
		axes.set_xlim(XL)

	@staticmethod
	def autoscale_y(axes):
		y0, y1 = axes.dataLim.intervaly
		YL = axes.yaxis.get_major_locator().view_limits(y0, y1)
		axes.set_ylim(YL)

	def draw_markers(self):
		for marker in self.parent.markers:
			self.draw_marker(marker)

	def draw_marker(self, marker):
		raise NotImplementedError

	def adjust_time(self, offset, factor=1.):
		self.time_offset = offset
		self.time_factor = factor


class XAxisHandling(object):
	xlim_callback_ext = None
	xlim_min = 0.
	xlim_max = 1.
	xlim_auto = True
	xlog = False

	def get_axes_requirements(self):
		return [AxesRequirements(size=self.size, independent_x=True)]

	def xlim_callback(self, ax):
		self.xlim_min, self.xlim_max = ax.get_xlim()
		if self.xlim_callback_ext:
			self.xlim_callback_ext(ax)

	def set_xlim_callback(self, func):
		self.xlim_callback = func

	def set_xlim(self, min, max, auto):
		self.xlim_min = min
		self.xlim_max = max
		self.xlim_auto = auto
		try:
			self.xlim_rescale()
		except util.SharedXError:
			# this is needed for graphs that can enable/disable the shared x axis
			pass
		if self.axes:
			return self.axes.get_xlim()
		else:
			return self.xlim_min, self.xlim_max

	def xlim_rescale(self):
		if not self.axes:
			return
		if self.xlim_auto:
			self.autoscale_x(self.axes)
		else:
			self.axes.set_xlim(self.xlim_min, self.xlim_max)

	def set_xlog(self, xlog):
		self.xlog = xlog
		if self.axes:
			self.axes.set_xscale('log' if xlog else 'linear')
		if self.secondaryaxes:
			self.secondaryaxes.set_xscale('log' if xlog else 'linear')


class YAxisHandling(object):
	ylim_callback_ext = None
	ylim_min = 0.
	ylim_max = 1.
	ylim_auto = True
	ylog = False

	def ylim_callback(self, ax):
		self.ylim_min, self.ylim_max = ax.get_ylim()
		if self.ylim_callback_ext:
			self.ylim_callback_ext(ax)

	def set_ylim_callback(self, func):
		self.ylim_callback_ext = func

	def set_ylim(self, min, max, auto):
		self.ylim_min = min
		self.ylim_max = max
		self.ylim_auto = auto
		self.ylim_rescale()
		if self.axes:
			return self.axes.get_ylim()
		else:
			return self.ylim_min, self.ylim_max

	def ylim_rescale(self):
		if not self.axes:
			return
		if self.ylim_auto:
			self.autoscale_y(self.axes)
		else:
			self.axes.set_ylim(self.ylim_min, self.ylim_max)

	def set_ylog(self, ylog):
		self.ylog = ylog
		if self.axes:
			self.axes.set_yscale('log' if ylog else 'linear')


class DoubleYAxisHandling(YAxisHandling):
	secondaryaxes = None

	ylim2_min = 0.
	ylim2_max = 1.
	ylim2_auto = True
	ylog2 = False

	def ylim_callback(self, ax):
		if ax is self.axes:
			self.ylim_min, self.ylim_max = ax.get_ylim()
		elif ax is self.secondaryaxes:
			self.ylim2_min, self.ylim2_max = ax.get_ylim()
		if self.ylim_callback_ext:
			self.ylim_callback_ext(ax)

	def set_ylim2(self, min, max, auto):
		self.ylim2_min = min
		self.ylim2_max = max
		self.ylim2_auto = auto
		self.ylim_rescale()
		if self.secondaryaxes:
			return self.secondaryaxes.get_ylim()
		else:
			return self.ylim2_min, self.ylim2_max

	def ylim_rescale(self):
		super(DoubleYAxisHandling, self).ylim_rescale()
		if not self.secondaryaxes:
			return
		if self.ylim2_auto:
			self.autoscale_y(self.secondaryaxes)
		else:
			self.secondaryaxes.set_ylim(self.ylim2_min, self.ylim2_max)

	def set_ylog2(self, ylog2):
		self.ylog2 = ylog2
		if self.secondaryaxes:
			self.secondaryaxes.set_yscale('log' if ylog2 else 'linear')

	def get_axes_requirements(self):
		return [AxesRequirements(size=self.size, twinx=True)]


class MultiTrendFormatter(object):
	counter = -1
	colors = 'bgrcmyk'

	def __call__(self, data):
		self.increase_counter()
		return self.colors[self.counter] + '-'

	def increase_counter(self):
		self.counter = (self.counter + 1) % len(self.colors)

	def reset(self):
		self.counter = -1


class MultiTrend(YAxisHandling, Subplot):
	legend = 'best'
	legendprops = matplotlib.font_manager.FontProperties(size='medium')

	def __init__(self, data=None, formatter=None):
		super(MultiTrend, self).__init__(data)
		if formatter is None:
			self.formatter = MultiTrendFormatter()
		else:
			if not isinstance(formatter, MultiTrendFormatter):
				raise TypeError("formatter must be a MultiTrendFormatter object (got '{0}')".format(formatter.__class__.__name__))
			self.formatter = formatter

	def setup(self):
		super(MultiTrend, self).setup()
		self.axes.callbacks.connect('ylim_changed', self.ylim_callback)

	def get_xdata(self, chandata):
		return self.time_factor*chandata.time + self.time_offset/86400.

	def get_ydata(self, chandata):
		return chandata.value

	def draw(self):
		if not self.data:
			return
		self.formatter.reset()
		for d in self.data.iterchannels():
			self.axes.plot(self.get_xdata(d), self.get_ydata(d), self.formatter(d), label=d.id)
		self.draw_legend()
		if self.ylog:
			self.axes.set_yscale('log')

	def clear(self, quick=False):
		if not quick:
			if self.axes:
				del self.axes.lines[:]
				self.axes.relim()
		super(MultiTrend, self).clear(quick)

	def set_legend(self, legend):
		self.legend = legend
		if legend:
			self.draw_legend()
		elif self.axes:
			self.get_legend_axes().legend_ = None

	def get_legend_items(self):
		return self.axes.get_legend_handles_labels()

	def get_legend_axes(self):
		return self.axes

	def draw_legend(self):
		if self.legend and self.axes:
			handles, labels = self.get_legend_items()
			if handles:
				self.get_legend_axes().legend(handles, labels, loc=self.legend, prop=self.legendprops)
			else:
				self.get_legend_axes().legend_ = None

	def draw_marker(self, marker):
		ax = self.axes
		if marker.interval():
			vspan = ax.axvspan(marker.left, marker.right, color='silver', zorder=-1e9)
			marker.add_callback(lambda: ax.patches.remove(vspan))
		else:
			line = ax.axvline(marker.left, color='silver', zorder=-1e9)
			marker.add_callback(lambda: ax.lines.remove(line))


class DoubleMultiTrend(MultiTrend, DoubleYAxisHandling):
	def __init__(self, data=None, secondarydata=None, formatter=None):
		self.secondarydata = secondarydata
		super(DoubleMultiTrend, self).__init__(data, formatter)

	def set_data(self, data, secondarydata=None):
		self.secondarydata = secondarydata
		super(DoubleMultiTrend, self).set_data(data)

	def setup(self):
		super(DoubleMultiTrend, self).setup()
		self.secondaryaxes.fmt_xdata = self.axes.fmt_xdata
		self.secondaryaxes.callbacks.connect('ylim_changed', self.ylim_callback)

	def draw(self):
		super(DoubleMultiTrend, self).draw()
		if self.secondarydata:
			for d in self.secondarydata.iterchannels():
				self.secondaryaxes.plot(self.get_xdata(d), self.get_ydata(d), self.formatter(d), label=d.id)
			self.draw_legend()
			if self.ylog2:
				self.secondaryaxes.set_yscale('log')

	def get_legend_items(self):
		# manually join the legends for both y-axes
		handles1, labels1 = self.axes.get_legend_handles_labels()
		handles2, labels2 = self.secondaryaxes.get_legend_handles_labels()
		return handles1 + handles2, labels1 + labels2

	def get_legend_axes(self):
		return self.secondaryaxes

	def set_axes(self, axes):
		self.axes, self.secondaryaxes = axes[0]

	def clear(self, quick=False):
		if not quick:
			if self.secondaryaxes:
				del self.secondaryaxes.lines[:]
				self.secondaryaxes.relim()
		super(DoubleMultiTrend, self).clear(quick)


class ImageBase(Subplot):
	colormap = 'spectral'
	interpolation = 'nearest'

	clim_min = 0.
	clim_max = 1.
	clim_auto = True
	clim_log = False

	def set_colormap(self, colormap):
		self.colormap = colormap
		if self.axes:
			for image in self.axes.images:
				image.set_cmap(colormap)

	def set_interpolation(self, interpolation):
		self.interpolation = interpolation
		if self.axes:
			for image in self.axes.images:
				image.set_interpolation(interpolation)

	def set_clim(self, min, max, auto, log):
		self.clim_min = min
		self.clim_max = max
		self.clim_auto = auto
		self.clim_log = log
		self.clim_rescale()

	def clim_rescale(self):
		if self.axes:
			for image in self.axes.images:
				# NOTE: it seems that a single instance of mpl.colors.Normalize isn't meant to be used for multiple images
				image.norm = self.get_clim_norm()

	def get_clim_norm(self):
		if self.clim_auto:
			min = max = None
		else:
			min = self.clim_min
			max = self.clim_max
		if self.clim_log:
			return matplotlib.colors.LogNorm(min, max)
		else:
			return matplotlib.colors.Normalize(min, max)


class Time2D(YAxisHandling, ImageBase):
	def draw(self):
		if not self.data:
			return

		for image in self.data.iterimages():
			self.axes.imshow(self.get_imdata(image), 
				origin='lower', extent=(image.tstart, image.tend, image.ybottom, image.ytop), aspect='auto',
				cmap=self.colormap, interpolation=self.interpolation, norm=self.get_clim_norm()
			)

		self.ylim_rescale()

	def clear(self, quick=False):
		if not quick and self.axes:
			del self.axes.images[:], self.axes.lines[:], self.axes.patches[:]
			self.axes.relim()

	def draw_marker(self, marker):
		shinysilver = (.75, .75, .75, .5)
		ax = self.axes
		if marker.interval():
			vspan = ax.axvspan(marker.left, marker.right, color=shinysilver, zorder=1e9)
			marker.add_callback(lambda: ax.patches.remove(vspan))
		else:
			line = ax.axvline(marker.left, color=shinysilver, zorder=1e9)
			marker.add_callback(lambda: ax.lines.remove(line))


class Image(ImageBase):
	colormap = 'afmhot'
	interpolation = 'nearest'
	tzoom = 1
	mode = 'film strip'
	rotate = False
	marker = None

	def __init__(self, *args, **kwargs):
		self.vspans = []
		super(Image, self).__init__(*args, **kwargs)

	def get_axes_requirements(self):
		if self.mode == 'single frame':
			return [AxesRequirements(size=self.size, independent_x=True)]
		else:
			return [AxesRequirements(size=self.size)]

	def setup(self):
		super(Image, self).setup()
		self.axes.set_yticks([])
		if self.mode == 'single frame':
			self.axes.set_xticks([])
			self.axes.fmt_xdata = None
	
	def draw(self):
		if not self.data:
			return

		for d in self.data.iterframes():
			# map the linenunumber to the time axis and the individual points to some arbitrary unit axis
			# transpose the image data to plot scanlines vertical
			ysize, xsize = d.image.shape[:2] # support NxM 'greyscale' images, NxMx3 RGB, and NxMx4 RGBA
			tstart = self.time_factor * d.tstart + self.time_offset / 86400.
			if d.tend is None:
				tend = None
			else:
				tend = self.time_factor * d.tend + self.time_offset / 86400.

			if self.mode == 'single frame':
				# somehow, origin=upper is not respected here for imshow, fix manually
				image = d.image[::-1,:]
				if self.rotate:
					image = numpy.rot90(image, 3)
				self.axes.imshow(image, aspect='equal', cmap=self.colormap, interpolation=self.interpolation)

				self.marker = self.parent.markers.add(tstart, tend)
			else:
				tendzoom = tstart + (tend - tstart) * self.tzoom
				self.axes.imshow(numpy.rot90(d.image), extent=(tstart, tendzoom, 0, 1), aspect='auto', cmap=self.colormap, interpolation=self.interpolation)
				self.axes.add_patch(matplotlib.patches.Rectangle((tstart, 0), tendzoom-tstart, 1, linewidth=1, edgecolor='black', fill=False))
	
		# imshow() changes the axes xlim/ylim, so go back to something sensible
		self.ylim_rescale()
		try:
			self.xlim_rescale()
		except util.SharedXError:
			pass
		# NOTE: IMHO the better solution is to change
		# matplotlib.image.ImageAxes.set_extent(); this should call
		# axes.autoscale_view(tight=True) instead of messing with the axes

	def ylim_rescale(self):
		self.autoscale_y(self.axes)

	def xlim_rescale(self):
		if self.mode == 'film strip':
			raise util.SharedXError
		self.autoscale_x(self.axes)

	def clear(self, quick=False):
		if not quick:
			if self.axes:
				del self.axes.lines[:], self.axes.images[:], self.axes.patches[:]
				self.axes.relim()
			if self.marker:
				self.parent.markers.remove(self.marker)
		self.marker = None
		super(Image, self).clear(quick)


	def set_rotate(self, rotate):
		if rotate == self.rotate:
			return
		self.rotate = rotate

		if self.axes and self.mode == 'single frame':
			im = self.axes.images[0]
			# NOTE this uses a feature that is not officially in the matplotlib API
			if rotate:
				im.set_data(numpy.rot90(im._A, 3))
			else:
				im.set_data(numpy.rot90(im._A))

	def draw_marker(self, left, right=None):
		pass

