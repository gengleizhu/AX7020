/* Link the unmodified upstream pkt_comm.c. Reserved bytes are explicitly zeroed. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pkt_comm.h"
void pkt_create_header(struct pkt *, unsigned char *);
PKT_CHECKSUM_TYPE pkt_checksum(unsigned char *, unsigned char *, int);
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *f = fopen(argv[1], "w");
    if (!f) return 3;
    for (int n = 1; n <= 65; ++n) {
        unsigned char h[14] = {0}, data[69];
        for (int i=0;i<n;++i) data[i]=(i*137+n*19)&255;
        struct pkt p = {0};
        p.version=2; p.type=(n%4)+1; p.id=0x1234+n; p.data_len=n;
        pkt_create_header(&p,h);
        pkt_checksum(h+10,h,10);
        pkt_checksum(data+n,data,n);
        for(int i=0;i<14;++i) fprintf(f,"%02x",h[i]);
        for(int i=0;i<n+4;++i) fprintf(f,"%02x",data[i]);
        fprintf(f,"\n");
    }
    fclose(f);
    return 0;
}
