
""" Example showing how to create a rational Bezier curve """


# -------------------------------------------------------------------------------------------------------------------- #
# Importing packages
# -------------------------------------------------------------------------------------------------------------------- #
import numpy as np
import nurbspy.jax as nrb
import matplotlib.pyplot as plt
from math import *
import ezdxf

# Maks Groom's dxf export function
def airfoil_to_dxf(points, filename="airfoil.dxf",close=True):
    """
    Create a DXF file from a sequence of airfoil points.

    Parameters
    ----------
    points : list of (x, y)
        Ordered airfoil coordinates.
    filename : str
        Output DXF filename.
    """
    # Create a new DXF drawing
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    # Add polyline using the points
    msp.add_lwpolyline(points, close=close)

    # Save file
    doc.saveas(filename)
    print(f"DXF saved to: {filename}")



# -------------------------------------------------------------------------------------------------------------------- #
# Based on the 2D rational Bezier curve example at https://github.com/turbo-sim/nurbspy
# -------------------------------------------------------------------------------------------------------------------- #
def leading_halfedge(T,LE,R):
    '''Define a rational Bezier curve for the leading edge of a foil.
    '''
    # Define the array of control points
    P = np.zeros((2,4))
    P[:, 0] = [0.0, 0.0]
    P[:, 1] = [0.0, T/2]
    P[:, 2] = [2*LE/3, T/2]
    P[:, 3] = [LE, T/2]
    # Define the array of control point weights
    W0 = 1
    W2 = 1
    W3 = 1
    W1 = sqrt(2*R*P[0,2]*W0*W2/(3*P[1,2]**2))
    W = np.asarray([W0,W1,W2,W3])
    bezier2D = nrb.NurbsCurve(control_points=P, weights=W)
    return bezier2D


def trailing_halfedge(T,TE,A):
    '''Define a rational Bezier curve for the trailing edge of a foil.
    '''
    # Define the array of control points
    P = np.zeros((2,5))
    P[:, 0] = [0.0, T/2]
    P[:, 1] = [TE/(2*2.5), T/2]
    P[:, 2] = [TE/2.5, T/2]
    P[:, 3] = [2/3*TE, TE/3*tan(A)]
    P[:, 4] = [TE, 0]
    W = np.asarray([1,1,1,1,1])
    bezier2D = nrb.NurbsCurve(control_points=P, weights=W)
    return bezier2D


class foil_half_edge():
    '''A class to facilitate piecewise assembly of an upper foil edge with
       two NURBS joined by a flat section.
    '''
    def __init__(self,chord=1,Tfrac=0.08,LEfrac=0.2,TEfrac=0.4,Rfrac=0.05,A=pi/32,
                 Npts=32,setpars=True,scale=1):
        '''Parameters are fraction of chord length, except Rfrac which is a
           fraction of thickness (T), as in Saporito et al. 2020.
           Npts is the number of points to evaluate on each of the leading
           edge and trailing edge.
        '''
        self.chord = chord
        self.Tfrac = Tfrac
        self.TEfrac = TEfrac
        self.LEfrac = LEfrac
        self.Rfrac = Rfrac
        self.Npts = Npts
        self.A = A
        self.scale = scale
        if setpars:
            self.set_pars()

    def set_pars(self,chord=None,T=None,LE=None,TE=None,R=None,A=None,Npts=None):
        '''Set foil parameters, if provided; otherwise calculate them from
           percentage parameters as in Saporito et al. 2020 Appendix A.
           Arguments are interpreted as absolute dimensions, as distinct
           from the arguments in __init__ which are interpreted as fractions.
        '''
        if chord:
            self.chord = chord
        if T:
            self.T = T
        else:
            self.T = self.Tfrac * self.chord
        if LE:
            self.LE = LE
        else:
            self.LE = self.LEfrac * self.chord
        if TE:
            self.TE = TE
        else:
            self.TE = self.TEfrac * self.chord
        if R:
            self.R = R
        else:
            self.R = self.Rfrac * self.T
        if A:
            self.A = A
        if Npts:
            self.Npts = Npts
        # A set of points for parametric evaluation of the NURB coordinates
        self.u = np.linspace(0,1,self.Npts,dtype=np.float64)
        # Set the length of the flat section
        self.flat = self.chord - self.LE - self.TE

    def get_foil(self,template=False,offset=5.,thicknessTE=0):
        '''Calculate trailing and leading edge NURBs, and lay out Npts points along
           the chord equally spaced in the x-direction, using the parameters produced
           by set_pars.

           If template==False (default) a closed outline of the half-foil is generated. 
           If template==True, an outline of of a template with the half-foil cut out is generated.
           In that case, offset specifies the thickness of the template.
        '''
        # Calculate the leading and trailing edge NURBs
        self.bLE = leading_halfedge(self.T,self.LE,self.R)
        self.bTE = trailing_halfedge(self.T,self.TE,self.A)
        # Evaluate points along the leading and trailing edges, using parametric points u
        self.xLE, self.yLE = self.bLE.get_value(self.u)
        self.xTE, self.yTE = self.bTE.get_value(self.u)
        # x-positions of the trailing edge are offset by the lengths of the leading edge and flat
        self.xTE += self.LE + self.flat
        # Generate points along the flat section, to enable vertical slices through the foil
        self.xFlat = np.linspace(self.LE,self.LE+self.flat,self.Npts)
        self.yFlat_top = self.T/2*np.ones(self.Npts)
        # assemble shape
        if template: # generate female template with half-foil cut-out
            # adjust TE profile to give TE thickness
            self.yTE = self.T/2-(self.T/2-self.yTE)*(1-thicknessTE/self.T)
            # locate LE corners of the template
            x_templateLE = (self.xLE[0]-offset)*np.ones(2)
            y_templateLE = np.array([offset+self.T/2,0.])
            # locate TE corners of the template
            x_templateTE = np.array([self.xTE[-1],self.xTE[-1]+offset,self.xTE[-1]+offset])
            y_templateTE = np.array([0.,0.,(offset+self.T/2)])
            self.yFlat_bottom = (offset+self.T/2)*np.ones(self.Npts)
            # Assemble the half-foil in three sections (leading and trailing edges, with the
            # flat section between them)
            self.xs = np.concatenate([self.xLE,self.xFlat,self.xTE,x_templateTE,
                                      np.flip(self.xTE),np.flip(self.xFlat),np.flip(self.xLE),x_templateLE])
            self.ys = np.concatenate([self.yLE,self.yFlat_top,self.yTE,y_templateTE,
                                      self.yFlat_bottom,self.yFlat_bottom,self.yFlat_bottom,y_templateLE])
        else: # generate male outline of half-foil
            self.yFlat_bottom = np.zeros(self.Npts)
            # Assemble the half-foil in three sections (leading and trailing edges, with the
            # flat section between them)
            self.xs = np.concatenate([self.xLE,self.xFlat,self.xTE,np.flip(self.xTE),np.flip(self.xFlat),np.flip(self.xLE)])
            self.ys = np.concatenate([self.yLE,self.yFlat_top,self.yTE,self.yFlat_bottom,self.yFlat_bottom,self.yFlat_bottom])

    def plot(self,fig=None,ax=None,show=['LE','TE']):
        '''Plot the foil as defined by the current (xs,ys)
        '''
        if ax: # if no axis provided, make one
            self.ax = ax
        else:
            if fig: # if no figure provided, make one
                self.fig = fig
            else:
                self.fig = plt.figure()
            self.ax = self.fig.add_subplot(1,1,1)
        (self.line,) = self.ax.plot(self.xs,self.ys)
        if 'LE' in show:  # highlight leading edge
            (self.lineLE,) = self.ax.plot(self.xLE,self.yLE)
        if 'TE' in show:  # highlight leading edge
            (self.lineTE,) = self.ax.plot(self.xTE,self.yTE)
        
        self.ax.set_aspect(1.0)
        self.ax.grid()
        self.ax.set_xlabel("$x$ axis", fontsize=12, color="k", labelpad=12)
        self.ax.set_ylabel("$y$ axis", fontsize=12, color="k", labelpad=12)
        
    def dxfwrite(self,filename,close=True,scale=None,clip=0):
        '''Write upper half-edge to a dxf file.
        '''
        xs = self.xs.copy()
        ys = self.ys.copy()
        if clip > 0:
            inds = np.where(self.xs<clip)
            xs = self.xs[inds]
            ys = self.ys[inds]
        if clip < 0:
            inds = np.where(self.xs>-clip)
            xs = self.xs[inds]
            ys = self.ys[inds]
        if scale:
            self.scale = scale
        airfoil_to_dxf(np.column_stack([scale*xs.T,scale*ys.T]),filename=filename,close=close)
