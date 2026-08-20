10 rem lunalight phase 1: native c128 runtime model probe
15 rem wait argument $1780, results $17a0, rng table $1800. the
17 rem results block lives in the linker-owned scratch region, not
18 rem in the code region: at $1740 the rng code grew over it.
20 rr=6048:pl=16384:hh=4864:nn=2304
30 print"{clr}phase 1: native c128 runtime"
40 rem stage -> gateway window. must precede graphic 1, which moves the text
45 rem over the stage. bank 0 is mandatory: the stage is under basic lo rom, so
47 rem a bank 15 peek there reads rom rather than the payload just loaded.
50 bank0:forii=0tonn-1:pokehh+ii,peek(pl+ii):nextii:bank15
60 pokerr,76:pokerr+1,49:pokerr+2,50:pokerr+3,56
70 rem checksum the relocated player so later stages can prove it survived
80 ss=0:forii=0to491:ss=ss+peek(hh+ii):nextii
90 pokerr+4,ss-int(ss/256)*256:pokerr+5,int(ss/256):pokerr+22,1
100 rem reserve $2000-$3fff, lift the text clear, stay in 40 columns
110 graphic1:graphic0
120 rr=6048:hh=4864:tb=6144:wj=6016
130 ifpeek(215)and128thensys65375
140 uu=peek(45)+256*peek(46):pokerr+6,uu-int(uu/256)*256:pokerr+7,int(uu/256)
150 pokerr+22,2
160 rem two 2k charset slots inside the graphic 1 reserve
170 forii=0to7:poke8192+ii,170:poke10240+ii,85:nextii
175 rem the editor's interrupt reloads $d018 from its shadow at $0a2c, so the
177 rem shadow is the register that actually selects a charset. sleep 1 before
178 rem each readback so the check proves the value survives an interrupt.
180 poke2604,24:poke53272,24:sleep1:pokerr+8,peek(53272):pokerr+35,peek(2604)
190 poke2604,26:poke53272,26:sleep1:pokerr+9,peek(53272):pokerr+36,peek(2604)
200 poke2604,20:poke53272,21
210 pokerr+10,peek(8192):pokerr+11,peek(10240):pokerr+22,3
220 rem strings live in ram bank 1: churn the heap, then re-checksum bank 0
230 forjj=1to20:aa$="":forii=1to25:aa$=aa$+"luna":nextii:nextjj
240 bb=0:forii=0to491:bb=bb+peek(hh+ii):nextii
250 pokerr+12,bb-int(bb/256)*256:pokerr+13,int(bb/256):pokerr+22,4
260 rem rng: collect entropy, prove the table varies, prove refill rewrites it
270 sys5376
280 c1=peek(tb):c2=peek(tb+1)
290 dd=0:forii=0to63:ifpeek(tb+ii)<>c1thendd=dd+1
300 nextii:pokerr+14,dd
310 sys5379:pokerr+15,-((peek(tb)<>c1)or(peek(tb+1)<>c2)):pokerr+22,5
320 rem fixed jiffy wait, argument at its c128 home instead of $02a7
330 t1=ti:k1=peek(162):pokewj,30:sys5388:t2=ti:k2=peek(162)
340 ee=t2-t1:pokerr+16,ee-int(ee/256)*256
350 kk=k2-k1:ifkk<0thenkk=kk+256
360 pokerr+17,kk
365 rem the same wait at a different count, to show the error does not scale
370 t1=ti:pokewj,60:sys5388:t2=ti:ff=t2-t1
375 pokerr+32,ff-int(ff/256)*256
380 rem loop length the player publishes, in jiffies, for the attract hand-off
385 pokerr+33,peek(4870):pokerr+34,peek(4871):pokerr+22,6
390 rem title player: install, prove bump and movspr still work, uninstall
392 forii=0to62:poke3584+ii,255:nextii
394 sprite1,1,1,0,0,0,0:movspr1,300,120
396 sys4864:sleep2
398 pokerr+18,peek(54296)
400 char0,10,20,chr$(18)+"    "
410 zz=bump(2):movspr1,104,210:sleep1
420 pokerr+19,bump(2)
430 xx=rsppos(1,0):pokerr+20,-(xx=104)
440 sys4867:sleep1:pokerr+21,peek(54296):pokerr+22,7
470 rem joystick port 2 read while the c128 keyboard scan is running
480 pokerr+24,peek(56320):pokerr+25,peek(56320)
490 rem editor and keyboard locations: record candidates, assume nothing
500 print"{home}"
510 forii=1to7:print:nextii
520 pokerr+26,peek(214):pokerr+27,peek(235):pokerr+28,peek(236)
530 pokerr+29,peek(2604):pokerr+30,peek(648):pokerr+31,peek(653)
540 pokerr+22,8
550 print"{clr}phase 1: native c128 runtime"
560 print"txttab";peek(rr+6)+256*peek(rr+7)
570 print"player sum";peek(rr+4)+256*peek(rr+5);"then";peek(rr+12)+256*peek(rr+13)
580 print"d018";peek(rr+8);peek(rr+9);"shadow";peek(rr+35);peek(rr+36)
585 print"pat";peek(rr+10);peek(rr+11)
590 print"rng spread";peek(rr+14);"refill";peek(rr+15)
600 print"wait30 ti";peek(rr+16);"jif";peek(rr+17);"wait60";peek(rr+32)
605 print"loop jiffies";peek(rr+33)+256*peek(rr+34)
610 print"sid on";peek(rr+18);"off";peek(rr+21);"bump";peek(rr+19)
620 print"joy";peek(rr+24);peek(rr+25)
630 print"row 214";peek(rr+26);"235";peek(rr+27);"236";peek(rr+28)
640 print"scr 2604";peek(rr+29);"648";peek(rr+30);"key 653";peek(rr+31)
650 pokerr+23,255:print"phase 1 done"
660 end
