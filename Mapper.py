import sys
from PIL import Image, ImageDraw
from geopy.distance import distance
from math import modf 
from math import floor
from math import ceil
import os


def convert( decimal ):

    dec_part,int_part = modf(decimal)
    deg = int(int_part)
    min = abs( int( modf( dec_part * 60 )[1] ))
    sec = abs( round( modf( dec_part * 60 )[0] * 60,1 ))
    return deg,min,sec


def get_distance( coord1,coord2 ):
        return distance(coord1,coord2).km

script_folder=os.path.dirname(__file__)
#project_folder=os.path.dirname(script_folder)
path = script_folder + '/pieces/'

bl_latitude  = br_latitude  = 42.883889
bl_longitude = tl_longitude = 12.848889
tl_latitude  = tr_latitude  = 42.967219
tr_longitude = br_longitude = 12.934281

bl_lat  = br_lat  = convert( bl_latitude  )
bl_long = tl_long = convert( bl_longitude )
tl_lat  = tr_lat  = convert( tl_latitude  )
tr_long = br_long = convert( tr_longitude )  

print("Top Left Coord. -> Lat: " + str( tl_lat[0] )+'° ' + str( tl_lat[1] )+'\' ' + str( tl_lat[2] )+'", Long: ' + str( tl_long[0] )+'° ' + str( tl_long[1] )+'\' ' + str( tl_long[2] )+'"')
print("Bottom Left Coord. -> Lat: " + str( bl_lat[0] )+'° ' + str( bl_lat[1] )+'\' ' + str( bl_lat[2] )+'", Long: ' + str( bl_long[0] )+'° ' + str( bl_long[1] )+'\' ' + str( bl_long[2] )+'"')
print("Top Right Coord. -> Lat: " + str( tr_lat[0] )+'° ' + str( tr_lat[1] )+'\' ' + str( tr_lat[2] )+'", Long: ' + str( tr_long[0] )+'° ' + str( tr_long[1] )+'\' ' + str( tr_long[2] )+'"')
print("Bottom Right Coord. -> Lat: " + str( br_lat[0] )+'° ' + str( br_lat[1] )+'\' ' + str( br_lat[2] )+'", Long: ' + str( br_long[0] )+'° ' + str( br_long[1] )+'\' ' + str( br_long[2] )+'"')

step   = 2048

km_height = get_distance((tl_latitude,tl_longitude), (bl_latitude,bl_longitude))
km_width  = get_distance((br_latitude,br_longitude), (bl_latitude,bl_longitude))
cm_height = round ( km_height * 100 / 25, 2 )
cm_width  = round ( km_width * 100 / 25, 2 )
width  = step * 3
height = step * 4

print( "Map Height: "+ str(cm_height)+ "cm, "+ str(height) +" pixels")
print( "Map Width: " + str(cm_width) + "cm, "+ str(width)  +" pixels")

dpcm = floor( width / cm_width )
print( "Dots per centimeter: "+str(dpcm) + " (rounded)") 

cm_latitude_interval  = round( get_distance( (43,12),(43.01666667,12)) *100 / 25, 4 ) #7.38
cm_longitude_interval = round( get_distance( (43,12),(43,12.01666667)) *100 / 25, 4 ) #5.42
print( str( cm_latitude_interval ) +' '+ str( cm_longitude_interval ) )
interval_dim = [ floor( cm_latitude_interval * dpcm ) , floor( cm_longitude_interval * dpcm ) ]
print("Pixel Dimension of Latitude and Longitude Intervals: " + str( interval_dim[0] ) + ", " + str( interval_dim[1] ) )

num_colonna = 0
new_im = Image.new('RGB', ( width, height ))
list_im = ['A.png','B.png','C.png','D.png']
for i in range( 0, width, step ):

        num_colonna += 1   

        
        for elem,j in zip( list_im, range( 0, height, step ) ):
                print("Opening " + str( num_colonna ) + elem)
                im = Image.open( path + str( num_colonna ) + elem )
                new_im.paste( im, (i,j) )

print("Saving...")
new_im.save( script_folder +'/'+ "Map.png")

#latitude_offset2 = floor( ( 60 - bl_lat[2] )/60 * cm_latitude_interval * dpcm )
latitude_offset1 = ceil(  tl_lat[2] /60 * interval_dim[0] )
latitude_offset2 = floor( ( 60 - bl_lat[2] )/60 * interval_dim[0] )
num_of_latitude_intervals = ( tl_lat[0] * 60 + tl_lat[1] ) - ( bl_lat[0] * 60 + bl_lat[1] ) - ( bl_lat[2] and 1 )
print("Number of pixels of the top most (incomplete) interval: "+ str( latitude_offset1) )
print("Number of pixels of the bottom most (incomplete) interval: "+ str( latitude_offset2) )
print("Number of Complete Latitude Intervals: " + str( num_of_latitude_intervals ) )

#longitude_offset2 = ceil( ( br_long[2] /60 * cm_longitude_interval * dpcm )
longitude_offset1 = floor( (60 - bl_long[2] )/60 * interval_dim[1] )
longitude_offset2 = ceil( br_long[2] /60 * interval_dim[1] )
num_of_longitude_intervals = ( br_long[0] * 60 + br_long[1] ) - ( bl_long[0] * 60 + bl_long[1] ) - ( bl_long[2] and 1 )
print("Number of pixels of the left most (incomplete) interval: "+ str( longitude_offset1 ) )
print("Number of pixels of the right most (incomplete) interval: "+ str( longitude_offset2 ) )
print("Number of Complete Longitude Intervals: " + str( num_of_longitude_intervals ) )

lat_error = height - latitude_offset1 - latitude_offset2 - num_of_latitude_intervals * interval_dim[0] 
long_error= width - longitude_offset1 - longitude_offset2 - num_of_longitude_intervals * interval_dim[1]
print( "Pixel Error in Latitude: " + str( lat_error ) ) 
print( "Pixel Error in Latitude: " + str( long_error ) )

if( lat_error % (num_of_latitude_intervals  +1) > dpcm * 0.4 or long_error % (num_of_longitude_intervals +1) > dpcm * 0.4):
        print( "WARNING!!! - total pixel error is greater than 4 mm" ) 


lat_error  = [ int ( lat_error  / ( num_of_latitude_intervals  +2 ) ), lat_error % (num_of_latitude_intervals  +2) ]

lat_pixel_adj = []
for i in range(0,num_of_latitude_intervals+1):
        lat_pixel_adj.append( lat_error[0] + ( 1 and lat_error[1] ) )
        lat_error[1] -= ( 1 and lat_error[1] )

long_error = [ int ( long_error / ( num_of_longitude_intervals +2 ) ), long_error % (num_of_longitude_intervals +2) ]
long_pixel_adj = []
for i in range(0,num_of_longitude_intervals+1):
        long_pixel_adj.append( long_error[0] + ( 1 and long_error[1] ) )
        long_error[1] -= ( 1 and long_error[1] ) 

latitude_intervals = []
latitude_intervals.append( latitude_offset1 + lat_pixel_adj[0] )
for i in range(1,num_of_latitude_intervals+1):
        latitude_intervals.append( interval_dim[0] + lat_pixel_adj[i] )
latitude_intervals.append( latitude_offset2 + lat_pixel_adj[ num_of_latitude_intervals ] )

longitude_intervals = []
longitude_intervals.append( longitude_offset1 + long_pixel_adj[0] )
for i in range(1,num_of_longitude_intervals+1):
        longitude_intervals.append( interval_dim[1] + long_pixel_adj[i] )
longitude_intervals.append( longitude_offset2 + long_pixel_adj[ num_of_longitude_intervals ] )

'''DEBUG CODE''''''
print( '         ' + str ( longitude_intervals[0] ) + ' ' + str ( longitude_intervals[1] ) + ' ' +  str ( longitude_intervals[2] ) + ' ' +  str ( longitude_intervals[3] ) + ' ' +  str ( longitude_intervals[4] ) + ' ' +  str ( longitude_intervals[5] ) + ' ' + str ( longitude_intervals[6] ))
print(str ( latitude_intervals[0] ))
print(str ( latitude_intervals[1] ))
print(str ( latitude_intervals[2] ))
print(str ( latitude_intervals[3] ))
print(str ( latitude_intervals[4] ))
print(str ( latitude_intervals[5] ))
'''

width2  = width  + 133
height2 = height + 133
im = Image.new('RGB', ( width2, height2 ), color="#ffffff")
mp_im = Image.open( script_folder +'/'+  "Mappa.png" )
im.paste( mp_im, (133,0) )
draw = ImageDraw.Draw( im )
draw.line( (0,0,0,height) ,width=61 ,fill= "#000000")
draw.line( (117,0,117,height) ,width=31 ,fill= "#000000")
j=0
flip_flop = 0
for i in latitude_intervals:

        k = j + i -1
        
        flip_flop = flip_flop != 1 
        if(flip_flop):
                draw.line( (66,j,66,k) ,width=72 ,fill= "#000000")
        else:
                draw.line( (66,j,66,k) ,width=72 ,fill= "#ffffff")
        
        j = k + 1

draw.line( (133, height + 15,  width2 ,height + 15) ,width=31 ,fill= "#000000")
draw.line( (133, height2 -15, width2, height2 - 15) ,width=31 ,fill= "#000000")


j=0
flip_flop = 0
for i in longitude_intervals:

        k = j + i -1
        
        flip_flop = flip_flop != 1 
        if(flip_flop):
                draw.line( (j + 133, height2 - 66, k + 133 , height2 - 66) ,width=75 ,fill= "#000000")
        else:
                draw.line( (j + 133, height2 - 66, k + 133 , height2 - 66) ,width=75 ,fill= "#ffffff")
                
        
        j = k + 1


draw.line( (134, height ,  134 ,height2) ,width=3 ,fill= "#000000")
draw.line( (width2, height ,  width2 ,height2) ,width=3 ,fill= "#000000")
draw.line( (0, 0,  132 ,0) ,width=3 ,fill= "#000000")
draw.line( (0, height -1 , 132, height -1) ,width=3 ,fill= "#000000")

print("Saving...")
mp_im.save( script_folder +'/'+ "Map_with_grid.png")

im.show()