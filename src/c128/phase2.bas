10 rem lunalight phase 2: vic bank 0 assets, sprites and the charset switch
15 rem assets come off disk, not out of this prg. graphic 1 zeroes bank 0 above
17 rem $4000, so nothing staged inside the program survives the relocation, and
19 rem the destinations sit under the text at load time. bload after graphic 1
21 rem is the only order that works, and it is the native c128 mechanism anyway.
30 print"{clr}phase 2: vic bank 0 assets"
40 graphic1:graphic0
50 rr=6048:pn=2040
60 bload"music",b0,p4864
70 bload"rng",b0,p5376
80 bload"charset",b0,p8192
90 bload"sprites",b0,p11900
100 pokerr,76:pokerr+1,49:pokerr+2,50:pokerr+3,56:pokerr+22,1
110 rem prove each region arrived at its own address
120 ss=.:forii=0to491:ss=ss+peek(4864+ii):nextii
130 pokerr+4,ss-int(ss/256)*256:pokerr+5,int(ss/256)
140 cs=.:forii=0to255:cs=cs+peek(8192+ii):nextii
150 pokerr+6,cs-int(cs/256)*256:pokerr+7,int(cs/256)
160 ps=.:forii=0to255:ps=ps+peek(11900+ii):nextii
170 pokerr+8,ps-int(ps/256)*256:pokerr+9,int(ps/256):pokerr+22,2
180 rem shapes the c64 title pointers resolve to, unchanged, in vic bank 0
190 s7=.:forii=0to63:s7=s7+peek(11968+ii):nextii
200 pokerr+26,s7-int(s7/256)*256:pokerr+27,int(s7/256)
210 s4=.:forii=0to63:s4=s4+peek(15552+ii):nextii
220 pokerr+28,s4-int(s4/256)*256:pokerr+29,int(s4/256):pokerr+22,3
230 rem title charset in the reserve, switched through the editor's shadow
240 poke2604,24:poke53272,24:sleep1
250 pokerr+10,peek(53272):pokerr+11,peek(2604):pokerr+22,4
260 rem the c64 title tableau: pointer values carried over unchanged
270 pokepn,187:pokepn+1,246:pokepn+2,253:pokepn+3,254
280 pokepn+4,243:pokepn+5,245:pokepn+6,195:pokepn+7,244
285 rem basic 7 colours run 1-16 where the vic registers run 0-15, so every
287 rem colour here is the c64 register value plus one. the c64 title writes
288 rem $d027-$d02e as 1,0,1,6,1,6,7,15; basic 7 wants 2,1,2,7,2,7,8,16.
290 rem enable and colour through basic 7, replacing the c64 register pokes
300 sprite1,1,2,0,0,0,0:sprite2,1,1,0,0,0,0
310 sprite3,1,2,0,0,0,0:sprite4,1,7,0,0,0,0
320 sprite5,1,2,0,0,0,0:sprite6,1,7,0,0,0,0
330 sprite7,1,8,0,0,0,0:sprite8,1,16,0,0,0,0
340 rem record before re-asserting, so the probe can tell whether sprite()
345 rem rewrites the pointers to its own $0e00 defaults
350 pokerr+12,peek(pn):pokerr+13,peek(pn+4)
360 pokepn,187:pokepn+4,243
370 movspr1,124,104:movspr2,124,104:movspr3,44,48:movspr4,44,48
380 movspr5,160,124:movspr6,160,124:movspr7,124,104:movspr8,180,52
390 sleep1
400 pokerr+14,peek(53269):pokerr+15,peek(pn):pokerr+16,peek(pn+4)
410 pokerr+17,peek(53248):pokerr+18,peek(53249):pokerr+24,peek(53264)
420 pokerr+19,peek(53287):pokerr+20,peek(53290):pokerr+22,5
430 rem attitude change: one pointer poke, no 64-byte block copy
440 pokepn,188:sleep1:pokerr+21,peek(pn):pokerr+22,6
450 rem $1c00-$1fff free after the relocation: pattern must survive heap churn
460 poke7168,171
470 forjj=1to20:aa$="":forii=1to25:aa$=aa$+"luna":nextii:nextjj
480 pokerr+30,peek(7168):pokerr+22,7
490 print"{clr}phase 2: vic bank 0 assets"
500 print"music";peek(rr+4)+256*peek(rr+5);"charset";peek(rr+6)+256*peek(rr+7)
510 print"sprites";peek(rr+8)+256*peek(rr+9)
520 print"slot187";peek(rr+26)+256*peek(rr+27);"slot243";peek(rr+28)+256*peek(rr+29)
530 print"d018";peek(rr+10);"shadow";peek(rr+11);"d015";peek(rr+14)
540 print"ptr0";peek(rr+12);peek(rr+15);"swap";peek(rr+21)
550 print"x";peek(rr+17);"y";peek(rr+18);"msb";peek(rr+24)
560 print"col";peek(rr+19);peek(rr+20);"$1c00";peek(rr+30)
570 pokerr+23,255:print"phase 2 done"
580 end
