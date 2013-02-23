#!/usr/bin/python
# -*- coding: utf-8 -*-


import numpy as np
import cairo
from time import time as time
import sys
from scipy.sparse import coo_matrix
from scipy.spatial import Delaunay,distance


def timeit(method):
  def timed(*args, **kw):
    ts = time()
    result = method(*args, **kw)
    te = time()
    print '\n{:s} took {:2.2f} sec\n'\
            .format(method.__name__,te-ts)
    return result
  return timed


@timeit
def main():
  """
  time to load up the ponies
  """

  ## numpy functions

  cos       = np.cos
  sin       = np.sin
  arctan2   = np.arctan2
  sqrt      = np.sqrt
  random    = np.random.random
  pi        = np.pi
  ft        = np.float64
  bigint    = np.int64
  ones      = np.ones
  zeros     = np.zeros
  array     = np.array
  bool      = np.bool
  tile      = np.tile
  maximum   = np.maximum
  colstack  = np.column_stack
  triag     = Delaunay
  unique    = np.unique
  positive  = lambda a: a[a>-1]
  vectorize = np.vectorize
  logicNot  = np.logical_not
  square    = np.square
  linspace  = np.linspace
  cdist     = distance.cdist

  ## GLOBAL-ISH CONSTANTS (SYSTEM RELATED)
  
  ## pixel size of canvas
  SIZE   = 500
  ## background color (white)
  BACK   = 1.
  ## foreground color (black)
  FRONT  = 0.
  ## filename of image
  OUT    = './rework.1.img'
  ## size of pixels on canvas
  STP    = 1./SIZE
  ## center of canvas
  C      = 0.5
  ## radius of circle with source nodes
  RAD    = 0.4
  ## number of grains used to sand paint each vein node
  GRAINS = 2
  ## alpha channel when rendering
  ALPHA  = 1.
  ## because five is right out
  FOUR = 4

  ## GLOBAL-ISH CONSTANTS (PHYSICAL PROPERTIES)
  
  ## minimum distance between source nodes
  sourceDist  = 10.*STP
  ## vein nodes die when they get this close to a source node
  killzone    = 2.*STP
  ## radius of vein nodes when rendered
  veinNodeRad = 2.*STP
  ## maximum number of vein nodes
  vmax        = 2*1e7
  ## maximum number of source nodes
  smax        = 200
  ## widht of widest vein node when rendered
  rootW       = 40.*STP
  ## number of root (vein) nodes
  rootNodes   = 1


  def ctxInit():
    """
    make the drawing board
    """
    sur = cairo.ImageSurface(cairo.FORMAT_ARGB32,SIZE,SIZE)
    ctx = cairo.Context(sur)
    ctx.scale(SIZE,SIZE)
    ctx.set_source_rgb(BACK,BACK,BACK)
    ctx.rectangle(0,0,1,1)
    ctx.fill()
    return sur,ctx
  sur,ctx = ctxInit()


  def stroke(x,y):
    """
    draw dot for each (x,y)
    """
    ctx.rectangle(x,y,1./SIZE,1./SIZE)
    ctx.fill()
    return
  vstroke = vectorize(stroke)


  def circ(x,y,cr):
    """
    draw circle for each (x,y) with radius cr
    """
    ctx.arc(x,y,cr,0,2.*pi)
    ctx.fill()
    return
  vcirc = vectorize(circ)


  def draw(P,W,oo):
    """
    draws the veins
    """

    ## simple vein W
    for i in reversed(xrange(rootNodes,oo)):
      ii = P[i]
      while ii>1:
        W[ii]+=1.
        ii = P[ii]

    wmax = W.max()
    W = sqrt(W/wmax)*rootW
    W[W<2.*STP] = 2.*STP

    ## show vein nodes
    for i in reversed(range(rootNodes-1,oo)):
      dx = X[P[i]]-X[i]
      dy = Y[P[i]]-Y[i]
      a  = arctan2(dy,dx)
      s  = linspace(0,1,GRAINS)*veinNodeRad
      xp = X[P[i]] - cos(a)*s
      yp = Y[P[i]] - sin(a)*s

      vcirc(xp,yp,[W[i]/2.]*GRAINS)


  def tesselation(tri,X,Y):
    """
    show triangulation of all vein nodes
    """

    for s in tri.simplices:
      ## ignore the four "container vertices" in the corners
      if np.all(s>FOUR-1):
        xy = tri.points[s,:]
        ctx.move_to(xy[0,0],xy[0,1])
        for i in xrange(2):
          ctx.line_to(xy[i,0],xy[i,1])
        ctx.stroke()


  def darts(xx,yy,rr,n):
    """
    get at most n random, uniformly distributed, points in a circle.
    centered at (xx,yy), with radius rr.
    """
    ## random uniform points in a circle
    t        = 2.*pi*random(n)
    u        = random(n)+random(n)
    r        = zeros(n,dtype=ft)
    mask     = u>1.
    xmask    = logicNot(mask)
    r[mask]  = 2.-u[mask]
    r[xmask] = u[xmask]
    xyp      = colstack(( rr*r*cos(t),rr*r*sin(t) ))
    gridxy   = xyp + array( [xx,yy] )

    o = []
    ## we only want points that have no neghbors 
    ## within radius sourceDist
    for i in xrange(n-1):
      dxy = gridxy[i,:] - gridxy[i+1:,:]
      dd  = sqrt(dxy[:,0]*dxy[:,0]+dxy[:,1]*dxy[:,1])
      if (dd > sourceDist).all():
        o.append(i)

    o = array(o,dtype=bigint)
    return gridxy[o,:]

 
  def makeNodemap(snum,ldistVS,ltri,lX,lY,lsXY):
    """
    nodemap[i,j] == True if vein node i is relative neighbor of 
    source node j
    u_i is relative neighbor of s if for all u_i:
      ||v-s|| < max{ ||u_i-s||, ||v-u_i|| }

      we save time by only checking the vein nodes that belong to the
      surounding simplices.
    """

    row = []
    col = []
    def listext(i,j):
      row.extend(i)
      col.extend(j)

    getSimplex = ltri.find_simplex

    for j in xrange(snum):
      simplex    = getSimplex(lsXY[j,:])
      nsimplices = positive( ltri.neighbors[simplex].flatten() )
      vertices   = positive( ltri.simplices[nsimplices,:].flatten() )
      ii         = unique(positive(vertices-FOUR)) # 4 initial nodes in tri
      iin        = ii.shape[0]

      if iin:

        ## distance: vein nodes -> vein nodes
        xy      = colstack((X[ii],Y[ii]))
        idistVV = cdist(xy,xy,'euclidean')
        
        idistVS = tile( ldistVS[ii,j],(iin,1) ).T
        mas     = maximum( idistVV,ldistVS[ii,j] )
        compare = idistVS < mas
        count   = compare.sum(axis=1)
        mask    = count==(iin-1)
        maskn   = mask.sum() 

        if maskn > 0:
          listext( list(ii[mask]),[j]*maskn )
    
    nodemap = coo_matrix( ( [True]*len(col),(row,col) ),\
                shape=(oo,snum),dtype=bool ).tocsr()

    return nodemap


  ### INITIALIZE

  ## arrays

  X = zeros(vmax,dtype=ft)
  Y = zeros(vmax,dtype=ft)
  P = zeros(vmax,dtype=bigint)-1
  W = zeros(vmax,dtype=float)

  sXY  = darts(C,C,RAD,smax)
  snum = sXY.shape[0]

  distVS  = None
  nodemap = None

  ## (START) VEIN NODES

  ## triangulation needs at least four initial points
  ## in addition we need the initial triangulation 
  ## to contain all source nodes
  ## remember that ndoes in tri will be four indices higher than in X,Y

  oo = rootNodes
  xinit = zeros( (rootNodes+FOUR,1) )
  yinit = zeros( (rootNodes+FOUR,1) )

  ## don't change
  xinit[0] = 0.; yinit[0] = 0.
  xinit[1] = 1.; yinit[1] = 0.
  xinit[2] = 1.; yinit[2] = 1.
  xinit[3] = 0.; yinit[3] = 1.
  
  for i in xrange(rootNodes):
    t = random()*2.*pi
    s = .1 + random()*0.7
    #x = C  + cos(t)*RAD*s
    #y = C  + sin(t)*RAD*s
    x = C
    y = C

    xinit[i+FOUR] = x
    yinit[i+FOUR] = y
    X[i]          = x
    Y[i]          = y

  tri = triag(colstack( (xinit,yinit) ),incremental=True)

  ### MAIN LOOP

  itt  = 0
  aggt = 0
  iti = time()
  try:
    while True:
      itt += 1

      ## distance: vein nodes -> source nodes
      del(distVS)
      xy     = np.column_stack((X[:oo],Y[:oo]))
      distVS = cdist(xy,sXY,'euclidean')
      
      ## this is where the magic might happen
      del(nodemap)
      nodemap = makeNodemap(snum,distVS,tri,X,Y,sXY)

      ## grow new vein nodes
      cont = False
      ooo = oo
      for i in xrange(oo):
        mask = nodemap[i,:].nonzero()[1]
        if mask.any():
          cont = True
          tx    = ( X[i]-sXY[mask,0] ).sum()
          ty    = ( Y[i]-sXY[mask,1] ).sum()
          a     = arctan2(ty,tx)
          X[oo] = X[i] - cos(a)*veinNodeRad
          Y[oo] = Y[i] - sin(a)*veinNodeRad
          P[oo] = i
          oo += 1
        
      ## add new points to triangulation
      tri.add_points(colstack((X[ooo:oo],Y[ooo:oo])))

      ## terminate if nothing happened.
      if not cont:
        break

      ## mask out dead source nodes
      sourcemask = ones(snum,dtype=bool)
      for j in xrange(snum):
        vinds = nodemap[:,j].nonzero()[0]
        if (distVS[vinds,j]<killzone).all():
          sourcemask[j] = False

      ## remove dead soure nodes
      sXY   = sXY[sourcemask,:]
      snum = sXY.shape[0]

      if not itt % 50:
        aggt += time()-iti
        print("""#i: {:6d} | #s: {:7.2f} | """\
              """#vn: {:6d} | #sn: {:6d}"""\
               .format(itt,aggt,oo,snum))
        sys.stdout.flush()
        iti = time()

  except KeyboardInterrupt:
    pass

  finally:

    #ctx.set_line_width(1./SIZE)
    #ctx.set_source_rgba(1.,0,0,0.7)

    #tesselation(tri,X,Y)

    ## set color
    ctx.set_source_rgb(FRONT,FRONT,FRONT)

    ## draws all vein nodes in
    draw(P,W,oo)

    ## save to file
    sur.write_to_png('{:s}.veins.png'.format(OUT))

    ## set line W if using lines

    #ctx.set_source_rgb(BACK,BACK,BACK)
    #ctx.rectangle(0,0,1,1)
    #ctx.fill()

    #sur.write_to_png('{:s}.tesselation.png'.format(OUT))
    
    ## draw nodes as circles
    #vcirc(X[:oo],Y[:oo],[veinNodeRad/2.]*oo)

    ## show source nodes
    #ctx.set_source_rgb(1,0,0)
    #vcirc(sX,sY,[sourceDist/2.]*len(sX))
    #ctx.set_source_rgb(FRONT,FRONT,FRONT)

  return


if __name__ == '__main__' : main()
