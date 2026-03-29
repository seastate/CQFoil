
""" Develop foil sections based on polynomials """

# ------------------------------------------------------------ #
# Importing packages
# ------------------------------------------------------------ #
import numpy as np
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

#------------------------------------------------------------------------
# Foil sections parameterized as in Pollock (1987) with correction by Mik Storer
#------------------------------------------------------------------------
def leading_halfedgeP(T,LE,U):
    '''Calculate XY points defining the leading edge of a foil.
    '''
    # X- and Y-coordinates defining leading edge, where U is position normalized by LE
    U2 = U**2  # square the x-coordinate to better resolve sqrt at LE
    xLE = LE * U2
    yLE = T/2 * (8/3*np.sqrt(U2) - 2*U2 + 1/3*U2**2 )
    #print(f'xLE = {xLE}')
    #print(f'yLE = {yLE}')
    return xLE,yLE

def trailing_halfedgeP(T,TE,U):
    '''Calculate XY points defining the leading edge of a foil.
    '''
    # X- and Y-coordinates defining trailing edge, where U is position starting at
    # the beginning of the taper and normalized by TE
    xTE = TE * U
    yTE = T/2 * (1 - 3/2*U**2 + 1/2*U**3)
    return xTE,yTE

class foil_half_edgeP():
    '''A class to facilitate piecewise assembly of an upper foil edge with
       two polynomial sections joined by a flat section, as outlined by Michael
       Storer. This follows the parameterization of Pollock (1987), with the angle
       parameter S=0 and correction of the trailing edge position coordinate (which
       is reversed in the original publication).
    '''
    def __init__(self,chord=1,Tfrac=0.08,LEfrac=0.2,TEfrac=0.4,Npts=32,setpars=True,scale=1):
        '''Parameters are fraction of chord length. Npts is the number of points to evaluate
           on each of the leading edge and trailing edge.
        '''
        self.chord = chord
        self.Tfrac = Tfrac
        self.TEfrac = TEfrac
        self.LEfrac = LEfrac
        self.Npts = Npts
        self.scale = scale
        if setpars:
            self.set_pars()

    def set_pars(self,chord=None,T=None,LE=None,TE=None,R=None,A=None,Npts=None):
        '''Set foil parameters, if provided; otherwise calculate them from
           percentage parameters as in Saporito et al. (2020) Appendix A.
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
        if Npts:
            self.Npts = Npts
        # A set of points for parametric evaluation of the polynomial coordinates
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
        # Evaluate points along the leading and trailing edges, using parametric points u
        self.xLE, self.yLE = leading_halfedgeP(self.T,self.LE,self.u)
        self.xTE, self.yTE = trailing_halfedgeP(self.T,self.TE,self.u)
        # x-positions of the trailing edge are offset by the lengths of the leading edge and flat
        self.xTE += self.LE + self.flat
        # Generate points along the flat section, to enable vertical slices through the foil
        self.xFlat = np.linspace(self.LE,self.LE+self.flat,self.Npts)[1:-1] # omit endpoints
        self.yFlat_top = self.T/2*np.ones(self.Npts)[1:-1]
        # assemble shape
        if template: # generate female template with half-foil cut-out
            print('Generating template (female)')
            # adjust TE profile to give TE thickness
            self.yTE = self.T/2-(self.T/2-self.yTE)*(1-thicknessTE/self.T)
            # locate LE corners of the template
            x_templateLE = (self.xLE[0]-offset)*np.ones(2)
            y_templateLE = np.array([offset+self.T/2,0.])
            # locate TE corners of the template
            x_templateTE = np.array([self.xTE[-1],self.xTE[-1]+offset,self.xTE[-1]+offset])
            y_templateTE = np.array([0.,0.,(offset+self.T/2)])
            self.yFlat_bottom = (offset+self.T/2)*np.ones(self.Npts)[1:-1]
            # Assemble the half-foil in three sections (leading and trailing edges, with the
            # flat section between them)
            self.xs = np.concatenate([self.xLE,self.xFlat,self.xTE,x_templateTE,
                                      np.flip(self.xTE),np.flip(self.xFlat),np.flip(self.xLE),x_templateLE])
            self.ys = np.concatenate([self.yLE,self.yFlat_top,self.yTE,y_templateTE,
                                      np.full_like(self.yTE,offset+self.T/2),np.flip(self.yFlat_bottom),
                                      np.full_like(self.yLE,offset+self.T/2),y_templateLE])
        else: # generate male outline of half-foil
            print('Generating half-foil (male)')
            self.yFlat_bottom = np.zeros(self.Npts)[1:-1]
            # Assemble the half-foil in three sections (leading and trailing edges, with the
            # flat section between them)
            self.xs = np.concatenate([self.xLE,self.xFlat,self.xTE,
                                      np.flip(self.xTE),np.flip(self.xFlat),np.flip(self.xLE)])
            self.ys = np.concatenate([self.yLE,self.yFlat_top,self.yTE,
                                      0*self.yTE,np.flip(self.yFlat_bottom),0*self.yLE])

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
            inds = np.where(self.xs>self.chord+clip)
            #inds = np.where(self.xs>-clip)
            xs = self.xs[inds]
            ys = self.ys[inds]
        if scale:
            self.scale = scale
        airfoil_to_dxf(np.column_stack([scale*xs.T,scale*ys.T]),filename=filename,close=close)
