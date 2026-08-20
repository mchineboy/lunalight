10 rem lunalight phase 0: native c128 vic-iie bootstrap probe
15 rem results block at $1b00; the verifier reads it, humans read the screen
20 rr=6912:print"{clr}phase 0: native c128 probe"
30 pokerr,76:pokerr+1,49:pokerr+2,50:pokerr+3,56
40 tt=peek(45)+256*peek(46):pokerr+4,tt-int(tt/256)*256:pokerr+5,int(tt/256)
50 pokerr+22,1
60 rem reserve $2000-$3fff and lift basic text clear of the vic charset window
70 graphic1:graphic0
80 rr=6912:pokerr+22,2
90 uu=peek(45)+256*peek(46):pokerr+6,uu-int(uu/256)*256:pokerr+7,int(uu/256)
100 ifpeek(215)and128thensys65375
110 pokerr+8,peek(215):pokerr+22,3
120 rem load the $1300 gateway from data
130 hh=4864:readnn:forii=0tonn-1:readbb:pokehh+ii,bb:nextii
140 pokerr+22,4
150 rem ram under basic rom: write through, then read it back both ways
160 bank15:poke16896,111
170 pokerr+9,peek(16896)
180 bank0:pokerr+10,peek(16896):bank15
190 pokerr+22,5
200 rem mmu and vic bank state
210 pokerr+11,peek(54533):pokerr+12,peek(54534)
220 pokerr+13,peek(56576):pokerr+14,peek(53272)
230 pokerr+22,6
240 rem gateway: sys in, mmu round trip, i/o intact, return to basic
250 sys4864
260 pokerr+22,7
270 rem basic 7 sprites: movspr owns the $d010 msb
280 forii=0to62:poke3584+ii,255:nextii
290 sprite1,1,1,0,0,0,0
300 movspr1,300,120
310 xx=rsppos(1,0):pokerr+15,xx-int(xx/256)*256:pokerr+16,int(xx/256)
320 pokerr+17,peek(53264):pokerr+19,peek(2040)
322 rem force a real sprite-background hit: solid sprite over a lit cell
324 char0,10,20,chr$(18)+"    "
326 zz=bump(2):movspr1,104,210:sleep1
330 pokerr+18,bump(2):pokerr+22,8
340 rem irq chain install and restore: the title player's model
350 sys4867:sleep1
360 cc=peek(4939)+256*peek(4940):sys4870
370 dd=peek(4939)+256*peek(4940):sleep1
380 ee=peek(4939)+256*peek(4940)
390 pokerr+20,-(cc>0):pokerr+21,-(dd=ee):pokerr+22,9
400 print"txttab";tt;"->";uu
410 print"rom$4200";peek(rr+9);" ram$4200";peek(rr+10)
420 print"gate ram";peek(4932);peek(4933);peek(4934)
430 print"cfg";peek(4936);"->";peek(4937);" rast";peek(4938)
440 print"movspr x";xx;" d010";peek(rr+17);" bump";peek(rr+18)
450 print"irq";cc;dd;ee
460 pokerr+23,255:print"phase 0 done"
470 end
9000 rem gateway data replaced by tools/c128-build.py
